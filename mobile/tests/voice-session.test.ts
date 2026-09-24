/**
 * Regression tests for `lib/voice-session.ts` orchestration races that
 * a focused review previously fixed: a pending Start disposed on screen
 * exit, and End never blocked by an in-flight Mute, with teardown
 * shared across concurrent Ends.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { VoiceTestSession } from "../lib/voice-session";
import type { VoiceTestHandle, VoiceTestStatus } from "../lib/voice";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function makeHandle() {
  const muteBarrier = deferred<void>();
  const handle: VoiceTestHandle & { endCalls: number; muteRequests: boolean[] } = {
    endCalls: 0,
    muteRequests: [],
    async setMuted(muted: boolean) {
      handle.muteRequests.push(muted);
      await muteBarrier.promise;
    },
    async end() {
      handle.endCalls += 1;
    },
  };
  return { handle, failMute: (error: Error) => muteBarrier.reject(error) };
}

function makeSession(
  startVoiceTest: (onStatus: (status: VoiceTestStatus) => void) => Promise<VoiceTestHandle>,
  onStatus: (status: VoiceTestStatus) => void = () => undefined
) {
  let unsubscribed = false;
  const session = new VoiceTestSession(
    {
      startVoiceTest,
      getAppState: () => "active",
      addAppStateListener: () => () => {
        unsubscribed = true;
      },
    },
    onStatus
  );
  return { session, wasUnsubscribed: () => unsubscribed };
}

test("screen exit during a pending Start disposes the late session", async () => {
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { session, wasUnsubscribed } = makeSession(() => pending.promise);

  const startPromise = session.start();
  session.dispose();
  pending.resolve(handle);
  assert.equal(await startPromise, null, "overtaken start resolves to null");
  assert.equal(handle.endCalls, 1, "late session released exactly once");
  assert.ok(wasUnsubscribed(), "app-state listener removed on dispose");
});

test("Start followed by concurrent Ends shares one teardown", async () => {
  const { handle } = makeHandle();
  const { session } = makeSession(async (onStatus) => {
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return handle;
  });

  await session.start();
  await Promise.all([session.end(), session.end()]);
  await session.end();
  assert.equal(handle.endCalls, 1, "teardown runs exactly once");
});

test("End is not blocked by an in-flight Mute", async () => {
  const { handle, failMute } = makeHandle();
  const { session } = makeSession(async () => handle);

  await session.start();
  const mutePromise = session.setMuted(true);
  // End resolves while the mute toggle is still pending: End never
  // waits for Mute.
  await session.end();
  assert.equal(handle.endCalls, 1);
  failMute(new Error("Session ended while changing mute."));
  await assert.rejects(mutePromise, /Session ended while changing mute/);
  assert.equal(handle.endCalls, 1, "mute failure did not re-run teardown");
});
