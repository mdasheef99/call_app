/**
 * Regression tests for the actual native audio-test lifecycle
 * (`lib/voice.native.ts`) driven by mocked LiveKit room events.
 *
 * Covers the unexpected-disconnect corrections: cleanup after a remote
 * disconnect, disconnect during Start, exactly-once teardown under
 * concurrent End / Mute-in-flight races, truthful participant count
 * before connection, and connected/"live" only after mic publish.
 */
import "./helpers/livekit-mock";
import test from "node:test";
import assert from "node:assert/strict";
import {
  FakeRoom,
  RoomEvent,
  armHoldFetch,
  audioSession,
  flush,
  resetLiveKitMock,
  timeline,
} from "./helpers/livekit-mock";
import { startVoiceTest } from "../lib/voice.native";
import type { VoiceTestStatus } from "../lib/voice";
import { VoiceTestSession } from "../lib/voice-session";

function makeLiveSession(onStatus: (status: VoiceTestStatus) => void) {
  return new VoiceTestSession(
    {
      startVoiceTest: (nativeOnStatus, shouldAbort) =>
        startVoiceTest(
          (status) => {
            onStatus(status);
            nativeOnStatus(status);
          },
          shouldAbort
        ),
      getAppState: () => "active",
      addAppStateListener: () => () => undefined,
    },
    () => undefined
  );
}

function offCount(room: FakeRoom): number {
  return room.micCalls.filter((c) => c === false).length;
}

function collect() {
  const statuses: VoiceTestStatus[] = [];
  return {
    statuses,
    push: (status: VoiceTestStatus) => {
      statuses.push(status);
      timeline.push(`status:${status.state}`);
    },
    last: () => statuses[statuses.length - 1],
  };
}

/** Bounded microtask drain (no wall-clock): fails deterministically if the condition never holds. */
async function waitFor(cond: () => boolean, what: string): Promise<void> {
  for (let i = 0; i < 500 && !cond(); i++) await flush();
  assert.ok(cond(), what);
}

test("unexpected disconnect after connection releases resources and reports error, not ended", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  assert.equal(rec.last()?.state, "connected");

  const stopsBefore = audioSession.stopCalls;
  const removesBefore = room.removeAllListenersCalls;
  room.emit(RoomEvent.Disconnected);
  await flush();

  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.errorMessage, "Disconnected unexpectedly.");
  assert.equal(last?.participantCount, 0);
  assert.equal(room.micCalls[room.micCalls.length - 1], false, "mic disabled on cleanup");
  assert.equal(audioSession.stopCalls, stopsBefore + 1, "audio session stopped on cleanup");
  assert.ok(room.removeAllListenersCalls > removesBefore, "listeners removed on cleanup");
  assert.ok(room.disconnectCalls >= 1, "room disconnect attempted on cleanup");

  // End after an unexpected disconnect must not fake "ended" or re-clean.
  await handle.end();
  await flush();
  assert.equal(rec.last()?.state, "error", "error status survives End");
  assert.equal(audioSession.stopCalls, stopsBefore + 1, "cleanup ran exactly once");
  assert.equal(room.removeAllListenersCalls, removesBefore + 1, "listeners removed exactly once");
});

test("connected status (and live mic display) appears only after mic publish", async () => {
  resetLiveKitMock();
  const rec = collect();
  await startVoiceTest(rec.push);
  assert.ok(
    timeline.indexOf("mic:true") < timeline.indexOf("status:connected"),
    `expected mic publish before connected status, got: ${timeline.join(" -> ")}`
  );
  const prePublish = rec.statuses.filter(
    (s) => s.state === "requesting" || s.state === "connecting"
  );
  assert.ok(prePublish.length >= 2, "requesting/connecting observed before connected");
});

test("disconnect during Start rejects instead of returning a successful handle", async () => {
  resetLiveKitMock();
  const rec = collect();
  const hold = FakeRoom.armHoldConnect();
  const startPromise = startVoiceTest(rec.push);
  await hold.entered;
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded before connect");
  room.emit(RoomEvent.Disconnected);
  await flush();
  hold.release();
  await assert.rejects(startPromise, /Disconnected unexpectedly/);
  await flush();

  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.errorMessage, "Disconnected unexpectedly.");
  assert.ok(audioSession.stopCalls >= 1, "audio session stopped");
  assert.ok(room.removeAllListenersCalls >= 1, "listeners removed");
  assert.ok(!room.micCalls.includes(true), "microphone never published");

  // Truthful counts before connection: no room during token mint/setup.
  const requesting = rec.statuses.find((s) => s.state === "requesting");
  const connecting = rec.statuses.find((s) => s.state === "connecting");
  assert.equal(requesting?.participantCount, 0, "participantCount 0 while requesting");
  assert.equal(connecting?.participantCount, 0, "participantCount 0 while connecting pre-room");
});

test("concurrent and repeated Ends run teardown exactly once", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  await Promise.all([handle.end(), handle.end()]);
  await handle.end();
  await flush();

  assert.equal(rec.last()?.state, "ended");
  assert.equal(audioSession.stopCalls, 1, "audio session stopped exactly once");
  assert.equal(room.disconnectCalls, 1, "room disconnected exactly once");
  assert.equal(room.removeAllListenersCalls, 1, "listeners removed exactly once");
  assert.equal(
    room.micCalls.filter((enabled) => enabled === false).length,
    1,
    "mic disabled exactly once"
  );
});

test("End racing an in-flight Mute reports honestly and cleans once", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  // Call 1 = publish; call 2 = the mute toggle (held); call 3 = teardown.
  const hold = room.holdMicCall(2);
  const mutePromise = handle.setMuted(true);
  await flush();
  await handle.end();
  await flush();
  hold.release();
  await assert.rejects(mutePromise, /Session ended while changing mute/);
  await flush();

  assert.equal(rec.last()?.state, "ended", "End's terminal state stands");
  assert.equal(audioSession.stopCalls, 1, "cleanup ran once despite the mute race");
});

test("End waits for an in-flight unexpected-disconnect cleanup", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  // Call 1 = publish; call 2 = the cleanup's mic release (held), so the
  // unexpected-disconnect cleanup stalls in flight right after `settled`.
  const hold = room.holdMicCall(2);
  room.emit(RoomEvent.Disconnected);
  await flush();
  assert.equal(audioSession.stopCalls, 0, "cleanup still in flight at the mic release");

  let endSettled = false;
  const endPromise = handle.end().then(() => {
    endSettled = true;
  });
  await flush();
  assert.equal(endSettled, false, "End must wait until in-flight cleanup finishes");

  hold.release();
  await endPromise;
  await flush();
  assert.equal(endSettled, true, "End resolves after cleanup completes");

  const last = rec.last();
  assert.equal(last?.state, "error", "terminal status is error, never a false ended");
  assert.equal(last?.errorMessage, "Disconnected unexpectedly.");
  assert.ok(
    !rec.statuses.some((s) => s.state === "ended"),
    "no ended status is ever emitted after an unexpected disconnect"
  );
  assert.equal(
    room.micCalls.filter((enabled) => enabled === false).length,
    1,
    "mic released exactly once"
  );
  assert.equal(audioSession.stopCalls, 1, "audio session stopped exactly once");
  assert.equal(room.removeAllListenersCalls, 1, "listeners removed exactly once");
});

test("failed End (disconnect) can be retried", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  const origDisconnect = room.disconnect.bind(room);
  let attempts = 0;
  room.disconnect = async (...args: unknown[]) => {
    attempts += 1;
    if (attempts === 1) throw new Error("boom-disconnect");
    return (origDisconnect as (...a: unknown[]) => Promise<void>)(...args);
  };
  await assert.rejects(handle.end(), /boom-disconnect/);
  assert.equal(rec.last()?.state, "error");
  await handle.end();
  await flush();
  assert.equal(rec.last()?.state, "ended", "retry succeeds");
  assert.equal(attempts, 2, "cleanup retried");
});

test("failed End without mic failure marks cleanup retryable and keeps mic off", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  const origDisconnect = room.disconnect.bind(room);
  let attempts = 0;
  room.disconnect = async (...args: unknown[]) => {
    attempts += 1;
    if (attempts === 1) throw new Error("boom-disconnect");
    return (origDisconnect as (...a: unknown[]) => Promise<void>)(...args);
  };
  await assert.rejects(handle.end(), /boom-disconnect/);
  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.cleanupFailed, true, "End retry advertised");
  assert.ok(!last?.micUnconfirmed, "no mic flag: mic-off succeeded, mic stays off");
  assert.equal(room.micEffective, false, "mic effectively off");

  await handle.end(); // retry succeeds
  await flush();
  assert.equal(rec.last()?.state, "ended");
  assert.ok(!rec.last()?.cleanupFailed, "success clears the retry marker");
  assert.equal(attempts, 2, "cleanup retried");
});

test("unconfirmed teardown failure also marks cleanup retryable", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  room.failMicCall(2, new Error("boom-mic-off")); // call 1 = publish
  room.failMicCall(3, new Error("boom-mic-off-again")); // first End's fresh attempt
  await assert.rejects(handle.end(), /unconfirmed/i);
  const last = rec.last();
  assert.equal(last?.micUnconfirmed, true);
  assert.equal(last?.cleanupFailed, true, "End retry advertised alongside the mic warning");
});

test("session End retries a flag-free cleanup failure, then Start works", async () => {
  resetLiveKitMock();
  const statuses: VoiceTestStatus[] = [];
  const session = makeLiveSession((s) => statuses.push(s));
  await session.start();
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  const origDisconnect = room.disconnect.bind(room);
  let attempts = 0;
  room.disconnect = async (...args: unknown[]) => {
    attempts += 1;
    if (attempts === 1) throw new Error("boom-disconnect");
    return (origDisconnect as (...a: unknown[]) => Promise<void>)(...args);
  };
  await assert.rejects(session.end(), /boom-disconnect/);
  const failed = statuses[statuses.length - 1];
  assert.equal(failed.state, "error");
  assert.equal(failed.cleanupFailed, true, "retry reachable through the status");
  assert.ok(!failed.micUnconfirmed, "no mic flag: mic-off succeeded");

  await session.end(); // displayed-End retry through the retained handle
  await flush();
  assert.equal(attempts, 2, "displayed End retried cleanup");
  assert.ok(!statuses[statuses.length - 1]?.cleanupFailed, "success clears the marker");

  await session.start(); // Start allowed again after completed cleanup
  await flush();
  assert.notEqual(FakeRoom.last, room, "a new room opened after recovery");
  assert.equal(FakeRoom.last?.micEffective, true, "new session publishes normally");
});

test("mic-release failure never reports ended and can be retried", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  const origMic = room.localParticipant.setMicrophoneEnabled;
  let micAttempts = 0;
  room.localParticipant.setMicrophoneEnabled = async (enabled: boolean) => {
    if (!enabled) {
      micAttempts += 1;
      if (micAttempts === 1) throw new Error("boom-mic-off");
    }
    return origMic(enabled);
  };
  await assert.rejects(handle.end(), /boom-mic-off/);
  assert.equal(rec.last()?.state, "error");
  assert.ok(!rec.statuses.some((s) => s.state === "ended"), "no false ended");
  await handle.end();
  await flush();
  assert.equal(rec.last()?.state, "ended", "retry succeeds after mic release");
});

test("unexpected-disconnect mic-release failure makes End reject", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  const origMic = room.localParticipant.setMicrophoneEnabled;
  room.localParticipant.setMicrophoneEnabled = async (enabled: boolean) => {
    if (!enabled) throw new Error("boom-mic-off");
    return origMic(enabled);
  };
  room.emit(RoomEvent.Disconnected);
  await flush();
  assert.equal(rec.last()?.state, "error");
  await assert.rejects(handle.end(), /boom-mic-off|unconfirmed/i);
});

test("in-flight unmute cannot restore mic after End", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  await handle.setMuted(true);
  const hold = room.holdMicCall(3);
  const unmute = handle.setMuted(false);
  await flush();
  await handle.end();
  hold.release();
  await assert.rejects(unmute, /Session ended while changing mute/);
  await flush();
  assert.equal(rec.last()?.state, "ended");
  assert.equal(
    room.micCalls[room.micCalls.length - 1],
    false,
    "mic ends off despite late enable"
  );
});

/** Bounded microtask drain asserting End settles while the given gate stays held. */
async function assertEndSettlesWhileHeld(endPromise: Promise<void>, what: string): Promise<void> {
  let endSettled = false;
  const watched = endPromise.then(() => {
    endSettled = true;
  });
  for (let i = 0; i < 50 && !endSettled; i++) await Promise.resolve();
  assert.ok(endSettled, `End must not wait for the stalled ${what}`);
  await watched;
}

test("session End during a held token fetch resolves without waiting for it", async () => {
  resetLiveKitMock();
  const statuses: VoiceTestStatus[] = [];
  const session = makeLiveSession((s) => statuses.push(s));
  const fetchHold = armHoldFetch();
  const startPromise = session.start();
  await fetchHold.entered;
  await assertEndSettlesWhileHeld(session.end(), "token fetch");
  fetchHold.release(); // late token result arrives after End
  assert.equal(await startPromise, null, "late fetch result never opens a room");
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  assert.equal(room.connectCalls, 0, "no room opened");
  assert.ok(!room.micCalls.includes(true), "mic never published");
  assert.ok(
    !statuses.some((s) => s.state === "connected"),
    "never reported connected"
  );
});

test("session End during a held connection resolves without waiting for it", async () => {
  resetLiveKitMock();
  const statuses: VoiceTestStatus[] = [];
  const session = makeLiveSession((s) => statuses.push(s));
  const hold = FakeRoom.armHoldConnect();
  const startPromise = session.start();
  await hold.entered;
  await assertEndSettlesWhileHeld(session.end(), "connection");
  hold.release(); // late connect resolves after End
  assert.equal(await startPromise, null, "late connect never installs");
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  assert.ok(!room.micCalls.includes(true), "mic never published");
  assert.ok(
    !statuses.some((s) => s.state === "connected"),
    "never reported connected"
  );
});

test("session End during a held mic publication resolves without waiting for it", async () => {
  resetLiveKitMock();
  const statuses: VoiceTestStatus[] = [];
  const session = makeLiveSession((s) => statuses.push(s));
  const startPromise = session.start();
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  const hold = room.holdMicCall(1); // hold the publish
  await waitFor(() => room.micCalls.length >= 1, "publish entered");
  await assertEndSettlesWhileHeld(session.end(), "mic publication");
  hold.release(); // late publish resolves after End
  assert.equal(await startPromise, null, "late publish never installs");
  assert.equal(room.micEffective, false, "late publish cannot leave the mic enabled");
  assert.ok(
    !statuses.some((s) => s.state === "connected"),
    "never reported connected"
  );
});

test("abort right after the token fetch never connects or starts audio", async () => {
  // A late token result must not open a room: cancellation is checked
  // after the asynchronous fetch, before connect.
  resetLiveKitMock();
  const rec = collect();
  await assert.rejects(
    startVoiceTest(rec.push, () => true),
    /overtaken|aborted|background|disposed/i
  );
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  assert.equal(room.connectCalls, 0, "no room opened after an aborted fetch");
  assert.equal(audioSession.startCalls, 0, "audio session never started");
  assert.ok(!room.micCalls.includes(true), "microphone never published");
});

test("abort flipping on right after publish rejects instead of reporting connected", async () => {
  // Lock-in for the existing cancellation check after microphone
  // publication: the abort lands after publish resolves but before the
  // connected status, so Start must reject and the mic must end off.
  resetLiveKitMock();
  const rec = collect();
  let abortNow = false;
  const startPromise = startVoiceTest(rec.push, () => abortNow);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  const hold = room.holdMicCall(1);
  await waitFor(() => room.micCalls.length >= 1, "publish entered");
  abortNow = true;
  hold.release();
  await assert.rejects(startPromise);
  await flush();
  assert.ok(
    !rec.statuses.some((s) => s.state === "connected"),
    "no connected status after a post-publish abort"
  );
  assert.equal(room.micCalls[room.micCalls.length - 1], false, "mic ends off");
  assert.equal(room.micEffective, false, "mic effectively off");
});

test("failed mic-off on End reports release unconfirmed and stays retryable", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  room.failMicCall(2, new Error("boom-mic-off")); // call 1 = publish

  await assert.rejects(handle.end(), /unconfirmed/i);
  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.micUnconfirmed, true, "release shown as unconfirmed");
  assert.ok(!rec.statuses.some((s) => s.state === "ended"), "no false ended");
  assert.equal(room.micEffective, true, "mic may still be live");

  await handle.end();
  await flush();
  assert.equal(rec.last()?.state, "ended", "retry succeeds after mic release");
  assert.equal(room.micEffective, false, "mic effectively off after retry");
});

test("End retry after unexpected-disconnect mic-off failure attempts mic-off fresh", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  room.failMicCall(2, new Error("boom-mic-off")); // call 1 = publish
  room.failMicCall(3, new Error("boom-mic-off-again")); // first End's fresh attempt
  room.emit(RoomEvent.Disconnected);
  await flush();
  assert.equal(rec.last()?.micUnconfirmed, true);
  await assert.rejects(handle.end(), /unconfirmed/i);

  const offsAfterFirst = room.micCalls.filter((c) => c === false).length;
  await handle.end(); // displayed-End retry: must make a FRESH mic-off attempt
  await flush();
  assert.equal(
    room.micCalls.filter((c) => c === false).length,
    offsAfterFirst + 1,
    "retry calls mic-off again instead of rethrowing a stored error"
  );
  assert.equal(room.micEffective, false, "mic effectively off after retry");
  assert.equal(rec.last()?.state, "error", "unexpected end stays an error");
  assert.ok(!rec.last()?.micUnconfirmed, "success clears the uncertainty");
});

test("late-Unmute compensation failure recovers on End retry", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  await handle.setMuted(true);
  const hold = room.holdMicCall(3); // hold the unmute enable
  const unmute = handle.setMuted(false);
  await waitFor(() => room.micCalls.length >= 3, "unmute enable entered");
  room.failMicCall(5, new Error("boom-compensating-off"));
  await handle.end(); // teardown off (call 4) succeeds; terminal is ended
  hold.release(); // enable resolves late: mic effectively on behind "ended"
  await assert.rejects(unmute, /unconfirmed/i);
  await flush();
  assert.equal(room.micEffective, true, "mic left effectively on");

  // Recovery: a further End makes a fresh mic-off attempt even though a
  // previous End already resolved successfully.
  const offsBefore = room.micCalls.filter((c) => c === false).length;
  await handle.end();
  await flush();
  assert.equal(
    room.micCalls.filter((c) => c === false).length,
    offsBefore + 1,
    "retry calls mic-off again"
  );
  assert.equal(room.micEffective, false, "mic effectively off after retry");
  assert.equal(rec.last()?.state, "ended");
  assert.ok(!rec.last()?.micUnconfirmed, "success clears the uncertainty");
});

test("failed Start with mic-off failure returns a handle whose End retries mic-off", async () => {
  resetLiveKitMock();
  const rec = collect();
  const hold = FakeRoom.armHoldConnect();
  const startPromise = startVoiceTest(rec.push);
  await hold.entered;
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  room.failMicCall(1, new Error("boom-mic-off")); // cleanup's mic-off (publish never ran)
  room.emit(RoomEvent.Disconnected);
  await flush();
  hold.release();

  // Must RESOLVE with a recovery vehicle, not reject: a mic-off attempt
  // threw (the mic state is uncertain even though publish never ran),
  // and only End can retry it — throwing the room away would strand it.
  const handle = await startPromise;
  assert.equal(rec.last()?.state, "error");
  assert.equal(rec.last()?.micUnconfirmed, true);

  const offsBefore = room.micCalls.filter((c) => c === false).length;
  await handle.end(); // displayed-End retry: fresh mic-off attempt
  await flush();
  assert.equal(
    room.micCalls.filter((c) => c === false).length,
    offsBefore + 1,
    "retry calls mic-off again"
  );
  assert.equal(room.micEffective, false, "mic effectively off after retry");
  assert.ok(!rec.last()?.micUnconfirmed, "success clears the uncertainty");
});

test("session End retries an unconfirmed release until mic-off succeeds, then Start works", async () => {
  resetLiveKitMock();
  const statuses: VoiceTestStatus[] = [];
  const session = makeLiveSession((s) => statuses.push(s));
  await session.start();
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  room.failMicCall(2, new Error("boom-mic-off")); // call 1 = publish
  room.failMicCall(3, new Error("boom-mic-off-again")); // first End's fresh attempt
  room.emit(RoomEvent.Disconnected);
  await flush();
  assert.equal(statuses[statuses.length - 1]?.micUnconfirmed, true);
  await assert.rejects(session.end(), /unconfirmed/i);

  const offsAfterFirst = offCount(room);
  await session.end(); // displayed-End retry through the retained handle
  await flush();
  assert.equal(offCount(room), offsAfterFirst + 1, "displayed End retried mic-off");
  assert.equal(room.micEffective, false, "mic effectively off after retry");
  assert.ok(!statuses[statuses.length - 1]?.micUnconfirmed, "success clears the uncertainty");

  // Release confirmed: a fresh Start is allowed again (exactly one new room).
  await session.start();
  await flush();
  assert.notEqual(FakeRoom.last, room, "a new room opened after recovery");
  assert.equal(FakeRoom.last?.micEffective, true, "new session publishes normally");
});

test("session Start while release is unconfirmed recovers inline before opening a room", async () => {
  resetLiveKitMock();
  const statuses: VoiceTestStatus[] = [];
  const session = makeLiveSession((s) => statuses.push(s));
  await session.start();
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  room.failMicCall(2, new Error("boom-mic-off"));
  room.failMicCall(3, new Error("boom-mic-off-again")); // first End's fresh attempt
  room.emit(RoomEvent.Disconnected);
  await flush();
  await assert.rejects(session.end(), /unconfirmed/i);

  // No second room opens while the release is unresolved: Start ends the
  // old session first (fresh mic-off), and only then opens a new room.
  await session.start();
  await flush();
  assert.notEqual(FakeRoom.last, room, "exactly one new room after inline recovery");
  assert.equal(FakeRoom.last?.micEffective, true, "new session publishes normally");
  assert.ok(
    statuses.some((s) => s.state === "connected"),
    "recovered session reaches connected"
  );
});

test("session End recovers a late-Unmute compensation failure", async () => {
  resetLiveKitMock();
  const statuses: VoiceTestStatus[] = [];
  const session = makeLiveSession((s) => statuses.push(s));
  const handle = await session.start();
  assert.ok(handle, "live handle returned");
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  await session.setMuted(true);
  const hold = room.holdMicCall(3); // hold the unmute enable
  const unmute = session.setMuted(false);
  await waitFor(() => room.micCalls.length >= 3, "unmute enable entered");
  room.failMicCall(5, new Error("boom-compensating-off"));
  await session.end(); // succeeds; the native handle is dropped here
  hold.release(); // enable resolves late behind the successful End
  await assert.rejects(unmute, /unconfirmed/i);
  await flush();
  assert.equal(room.micEffective, true, "mic left effectively on");
  assert.equal(statuses[statuses.length - 1]?.micUnconfirmed, true);

  // Displayed End still works: the session retained the recovery handle.
  const offsBefore = offCount(room);
  await session.end();
  await flush();
  assert.equal(offCount(room), offsBefore + 1, "displayed End retried mic-off");
  assert.equal(room.micEffective, false, "mic effectively off after retry");
  assert.ok(!statuses[statuses.length - 1]?.micUnconfirmed, "success clears the uncertainty");
});

test("unexpected-disconnect mic-off failure is flagged unconfirmed", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  room.failMicCall(2, new Error("boom-mic-off")); // call 1 = publish
  room.failMicCall(3, new Error("boom-mic-off-again")); // first End's fresh attempt
  room.emit(RoomEvent.Disconnected);
  await flush();
  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.micUnconfirmed, true, "release shown as unconfirmed");
  assert.equal(room.micEffective, true, "mic may still be live");
  // The displayed End retries mic-off fresh (call 3) instead of
  // rethrowing the stored error — and still rejects while it keeps
  // failing, keeping the warning retryable rather than pinned.
  await assert.rejects(handle.end(), /boom-mic-off|unconfirmed/i);
  assert.equal(rec.last()?.micUnconfirmed, true, "warning retained after failed retry");
  assert.equal(room.micEffective, true, "mic still effectively on");
});

test("late publish after an unexpected disconnect is compensated; mic ends off", async () => {
  resetLiveKitMock();
  const rec = collect();
  const startPromise = startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  const hold = room.holdMicCall(1); // hold the publish
  await waitFor(() => room.micCalls.length >= 1, "publish entered");
  room.emit(RoomEvent.Disconnected); // teardown's own mic-off (call 2) runs first
  await flush();
  hold.release(); // publish(true) resolves late, behind a settled session
  await assert.rejects(startPromise, /Disconnected unexpectedly/);
  await flush();
  assert.equal(
    room.micCalls[room.micCalls.length - 1],
    false,
    "compensating mic-off runs after the late publish"
  );
  assert.equal(room.micEffective, false, "mic effectively off despite the late publish");
});

test("late publish with failing compensation surfaces release unconfirmed", async () => {
  resetLiveKitMock();
  const rec = collect();
  const startPromise = startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  const hold = room.holdMicCall(1);
  room.failMicCall(3, new Error("boom-compensating-off")); // the late compensating mic-off
  await waitFor(() => room.micCalls.length >= 1, "publish entered");
  room.emit(RoomEvent.Disconnected);
  await flush();
  hold.release();
  // Resolves with a recovery vehicle (not a rejection): the mic is
  // effectively on with no live handle, and only End can retry it.
  const handle = await startPromise;
  await flush();
  assert.equal(room.micEffective, true, "mic left effectively on");
  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.micUnconfirmed, true, "release shown as unconfirmed, not ended");
  assert.ok(!rec.statuses.some((s) => s.state === "ended"), "no false ended");

  // Displayed-End recovery: fresh mic-off attempt clears the uncertainty.
  const offsBefore = room.micCalls.filter((c) => c === false).length;
  await handle.end();
  await flush();
  assert.equal(
    room.micCalls.filter((c) => c === false).length,
    offsBefore + 1,
    "retry calls mic-off again"
  );
  assert.equal(room.micEffective, false, "mic effectively off after retry");
  assert.ok(!rec.last()?.micUnconfirmed, "success clears the uncertainty");
});

test("late Unmute racing End with failing compensation leaves mic on and unconfirmed", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  await handle.setMuted(true); // call 2 = mic off, effective off
  assert.equal(room.micEffective, false);
  const hold = room.holdMicCall(3); // hold the unmute enable
  const unmute = handle.setMuted(false);
  await waitFor(() => room.micCalls.length >= 3, "unmute enable entered");
  room.failMicCall(5, new Error("boom-compensating-off")); // the late compensating mic-off
  await handle.end(); // teardown off (call 4) succeeds; terminal state is ended
  assert.equal(rec.last()?.state, "ended");
  hold.release(); // enable resolves late: mic effectively on behind "ended"
  await assert.rejects(unmute, /unconfirmed/i);
  await flush();
  assert.equal(room.micEffective, true, "mic left effectively on");
  const last = rec.last();
  assert.equal(last?.state, "error", "unconfirmed error supersedes the stale ended");
  assert.equal(last?.micUnconfirmed, true, "release shown as unconfirmed");
});

test("aborted Start never publishes the microphone", async () => {
  resetLiveKitMock();
  const rec = collect();
  await assert.rejects(
    startVoiceTest(rec.push, () => true),
    /overtaken|aborted|background|disposed/i
  );
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  assert.ok(!room.micCalls.includes(true), "microphone never published when aborted");
  // Flip to aborted only after connect entered to cover mid-start race:
  resetLiveKitMock();
  const hold = FakeRoom.armHoldConnect();
  const rec2 = collect();
  let lateAbort = false;
  const p = startVoiceTest(rec2.push, () => lateAbort);
  await hold.entered;
  lateAbort = true;
  hold.release();
  await assert.rejects(p);
  assert.ok(!FakeRoom.last!.micCalls.includes(true), "late abort still prevents publish");
});
