/**
 * Regression tests for `lib/voice-session.ts` orchestration races that
 * a focused review previously fixed: a pending Start disposed on screen
 * exit, and End never blocked by an in-flight Mute, with teardown
 * shared across concurrent Ends.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { VoiceTestSession, VOICE_TEST_WATCHDOG_MS } from "../lib/voice-session";
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

/** Manual watchdog scheduler: firing is an explicit test step, never wall-clock. */
function makeScheduler() {
  let fire: (() => void) | null = null;
  let armedMs: number | null = null;
  let cancels = 0;
  let schedules = 0;
  return {
    schedules: () => schedules,
    cancels: () => cancels,
    armedMs: () => armedMs,
    pending: () => fire !== null,
    schedule: (cb: () => void, ms: number) => {
      schedules += 1;
      fire = cb;
      armedMs = ms;
      return () => {
        cancels += 1;
        fire = null;
      };
    },
    trigger: () => {
      const cb = fire;
      fire = null;
      assert.ok(cb, "watchdog must be armed when triggered");
      cb();
    },
  };
}

function makeSessionWithScheduler(
  startVoiceTest: (onStatus: (status: VoiceTestStatus) => void) => Promise<VoiceTestHandle>,
  scheduler: ReturnType<typeof makeScheduler>,
  appState: { current: string } = { current: "active" },
  onStatus: (status: VoiceTestStatus) => void = () => undefined
) {
  let listener: ((state: string) => void) | null = null;
  const session = new VoiceTestSession(
    {
      startVoiceTest,
      getAppState: () => appState.current,
      addAppStateListener: (onChange) => {
        listener = onChange;
        return () => {
          listener = null;
        };
      },
      scheduleWatchdog: scheduler.schedule,
    },
    onStatus
  );
  return {
    session,
    background: () => {
      assert.ok(listener, "app-state listener registered");
      listener("background");
    },
  };
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

test("failed session End retains handle so cleanup can be retried", async () => {
  let endCalls = 0;
  const handle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      if (endCalls === 1) throw new Error("boom-teardown");
    },
  };
  const { session } = makeSession(async () => handle as never);
  await session.start();
  await assert.rejects(session.end(), /boom-teardown/);
  await session.end();
  assert.equal(endCalls, 2, "retry re-runs teardown");
});

test("concurrent Starts are single-flight", async () => {
  let startCalls = 0;
  const { handle } = makeHandle();
  const { session } = makeSession(async () => {
    startCalls += 1;
    await new Promise((r) => setTimeout(r, 20));
    return handle;
  });
  const p1 = session.start();
  const p2 = session.start();
  const results = await Promise.allSettled([p1, p2]);
  const fulfilled = results.filter((r) => r.status === "fulfilled").length;
  const rejected = results.filter((r) => r.status === "rejected").length;
  assert.equal(startCalls, 1, "only one room opened");
  assert.equal(fulfilled, 1);
  assert.equal(rejected, 1);
});

test("watchdog default is the development-only 90-second bound", () => {
  assert.equal(VOICE_TEST_WATCHDOG_MS, 90_000);
});

test("watchdog fires 90 seconds after the Start tap", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { session } = makeSessionWithScheduler(() => pending.promise, scheduler);
  void session.start();
  assert.equal(scheduler.schedules(), 1, "watchdog armed once per Start tap");
  assert.equal(scheduler.armedMs(), 90_000, "development-only 90-second bound");
});

test("watchdog invalidates a pending Start so the late room is released", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { session } = makeSessionWithScheduler(() => pending.promise, scheduler);
  const startPromise = session.start();
  scheduler.trigger();
  assert.ok(!scheduler.pending(), "fired watchdog does not re-arm itself");
  pending.resolve(handle);
  assert.equal(await startPromise, null, "invalidated start resolves to null");
  assert.equal(handle.endCalls, 1, "late room released exactly once");
});

test("watchdog triggers End for a live handle", async () => {
  const scheduler = makeScheduler();
  const { handle } = makeHandle();
  const statuses: VoiceTestStatus[] = [];
  const { session } = makeSessionWithScheduler(
    async () => handle,
    scheduler,
    { current: "active" },
    (s) => {
      statuses.push(s);
    }
  );
  await session.start();
  assert.ok(scheduler.pending(), "watchdog stays armed while the session is live");
  scheduler.trigger();
  await new Promise((r) => setImmediate(r));
  assert.equal(handle.endCalls, 1, "live session ended by the watchdog");
});

test("End during a pending Start invalidates it instead of no-op", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { session } = makeSessionWithScheduler(() => pending.promise, scheduler);
  const startPromise = session.start();
  // Must resolve (not hang): End waits for the overtaken start to
  // settle, so resolve it concurrently — awaiting End first would
  // deadlock the test (and would stall a real caller the same way).
  const endPromise = session.end();
  pending.resolve(handle);
  await endPromise;
  assert.equal(await startPromise, null, "ended pending start resolves to null");
  assert.equal(handle.endCalls, 1, "late room released exactly once");
  assert.equal(scheduler.cancels(), 1, "timer cleared on End");
});

test("watchdog is cleared on End before it fires", async () => {
  const scheduler = makeScheduler();
  const { handle } = makeHandle();
  const { session } = makeSessionWithScheduler(async () => handle, scheduler);
  await session.start();
  await session.end();
  assert.equal(handle.endCalls, 1);
  assert.equal(scheduler.cancels(), 1, "timer cleared on End");
});

test("watchdog is cleared when Start fails", async () => {
  const scheduler = makeScheduler();
  const { session } = makeSessionWithScheduler(async () => {
    throw new Error("boom-start");
  }, scheduler);
  await assert.rejects(session.start(), /boom-start/);
  assert.equal(scheduler.cancels(), 1, "timer cleared on failure");
});

test("background clears the watchdog and invalidates a pending Start", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const appState = { current: "active" };
  const { session, background } = makeSessionWithScheduler(
    () => pending.promise,
    scheduler,
    appState
  );
  const startPromise = session.start();
  appState.current = "background";
  background();
  assert.equal(scheduler.cancels(), 1, "timer cleared on background");
  pending.resolve(handle);
  assert.equal(await startPromise, null, "backgrounded start resolves to null");
  assert.equal(handle.endCalls, 1, "late room released exactly once");
});

test("a second Start while one is pending does not re-arm the watchdog", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { session } = makeSessionWithScheduler(() => pending.promise, scheduler);
  const first = session.start();
  await assert.rejects(session.start(), /already in progress/);
  assert.equal(scheduler.schedules(), 1, "single-flight Start keeps one timer");
  pending.resolve(handle);
  assert.equal(await first, handle, "first Start still succeeds");
  scheduler.trigger();
  assert.equal(handle.endCalls, 1, "watchdog still guards the first tap's window");
});

test("Start is blocked while release is unconfirmed until End recovers", async () => {
  // A healthy End drops the handle; a failure that lands afterwards
  // (late mic-off compensation) has no handle to drop — the session
  // must still retain recovery, block Start, and route End to it.
  let push!: (status: VoiceTestStatus) => void;
  let startCalls = 0;
  let endCalls = 0;
  let endFails = false;
  const endedStatus: VoiceTestStatus = {
    state: "ended",
    muted: false,
    participantCount: 0,
    errorMessage: null,
  };
  const unconfirmedStatus: VoiceTestStatus = {
    state: "error",
    muted: false,
    participantCount: 0,
    errorMessage: "Microphone release unconfirmed: boom",
    micUnconfirmed: true,
  };
  const handle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      if (endFails) throw new Error("Microphone release unconfirmed: boom");
      push(endedStatus);
    },
  };
  const { session } = makeSession(async (onStatus) => {
    push = onStatus;
    startCalls += 1;
    return handle as never;
  });
  await session.start();
  await session.end(); // healthy End: handle dropped, recovery retained
  assert.equal(endCalls, 1);

  // Late mic-off failure after the successful End: no live handle exists.
  push(unconfirmedStatus);
  await assert.rejects(session.start(), /unconfirmed/i);
  assert.equal(startCalls, 1, "no second room while release is unresolved");

  // Displayed End routes to the retained recovery handle (fresh attempt).
  endFails = false;
  await session.end();
  assert.equal(endCalls, 2, "End retried through retained recovery");

  // Release confirmed: Start is allowed again.
  await session.start();
  assert.equal(startCalls, 2);
});

test("waiting Start does not open when the orphan's late cleanup reports unconfirmed", async () => {
  // End invalidates a pending Start; a second Start waits on the orphan;
  // the orphan's late disposal fails with an unconfirmed mic release.
  // The waiter must open no room, and the retained handle must stay
  // available for End retry.
  let push!: (status: VoiceTestStatus) => void;
  let calls = 0;
  let endCalls = 0;
  let endFails = true;
  const endedStatus: VoiceTestStatus = {
    state: "ended",
    muted: false,
    participantCount: 0,
    errorMessage: null,
  };
  const unconfirmedStatus: VoiceTestStatus = {
    state: "error",
    muted: false,
    participantCount: 0,
    errorMessage: "Microphone release unconfirmed: boom",
    micUnconfirmed: true,
  };
  const orphanHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      if (endFails) {
        push(unconfirmedStatus);
        throw new Error("Microphone release unconfirmed: boom");
      }
      push(endedStatus);
    },
  };
  const freshHandle = {
    async setMuted(_muted: boolean) {},
    async end() {},
  };
  const pending = deferred<VoiceTestHandle>();
  const { session } = makeSession(async (onStatus) => {
    push = onStatus;
    calls += 1;
    return (calls === 1 ? pending.promise : Promise.resolve(freshHandle)) as never;
  });
  const first = session.start();
  await session.end(); // invalidates + detaches; returns without waiting
  const secondPromise = session.start(); // waits on the orphan
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(calls, 1, "no second room while the orphan is unresolved");
  pending.resolve(orphanHandle); // orphan settles late → disposal fails unconfirmed
  await assert.rejects(secondPromise, /unconfirmed/i);
  assert.equal(calls, 1, "failed orphan cleanup opens no room");
  assert.equal(await first, null);
  assert.equal(endCalls, 1, "orphan disposal attempted once");

  // Retained handle stays available for End retry; success unblocks Start.
  endFails = false;
  await session.end();
  assert.equal(endCalls, 2, "End retried through the retained handle");
  await session.start();
  assert.equal(calls, 2, "Start allowed again after confirmed recovery");
});

test("waiting Start does not open when the orphan's late cleanup fails without a flag", async () => {
  // Same shape, but the late disposal fails with a plain room error
  // (mic-off succeeded; disconnect did not): no micUnconfirmed flag,
  // yet the room release is uncertain — a rejected end() is never
  // proven release, so no room may open and End must still retry it.
  let push!: (status: VoiceTestStatus) => void;
  let calls = 0;
  let endCalls = 0;
  let endFails = true;
  const endedStatus: VoiceTestStatus = {
    state: "ended",
    muted: false,
    participantCount: 0,
    errorMessage: null,
  };
  const plainErrorStatus: VoiceTestStatus = {
    state: "error",
    muted: false,
    participantCount: 0,
    errorMessage: "boom-disconnect",
  };
  const orphanHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      if (endFails) {
        push(plainErrorStatus);
        throw new Error("boom-disconnect");
      }
      push(endedStatus);
    },
  };
  const freshHandle = {
    async setMuted(_muted: boolean) {},
    async end() {},
  };
  const pending = deferred<VoiceTestHandle>();
  const { session } = makeSession(async (onStatus) => {
    push = onStatus;
    calls += 1;
    return (calls === 1 ? pending.promise : Promise.resolve(freshHandle)) as never;
  });
  const first = session.start();
  await session.end(); // invalidates + detaches; returns without waiting
  const secondPromise = session.start(); // waits on the orphan
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(calls, 1, "no second room while the orphan is unresolved");
  pending.resolve(orphanHandle); // orphan settles late → disposal fails flag-free
  await assert.rejects(secondPromise, /did not complete/i);
  assert.equal(calls, 1, "uncertain room release opens no room");
  assert.equal(await first, null);

  // End retry still reaches the retained handle despite no flag.
  endFails = false;
  await session.end();
  assert.equal(endCalls, 2, "End retried through the retained handle");
  await session.start();
  assert.equal(calls, 2, "Start allowed again after completed cleanup");
});

test("background permanently invalidates a pending Start even after foreground return", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const appState = { current: "active" };
  const { session, background } = makeSessionWithScheduler(
    () => pending.promise,
    scheduler,
    appState
  );
  const startPromise = session.start();
  appState.current = "background";
  background();
  // The app returns to the foreground BEFORE the pending await finishes:
  // the orphaned Start must still never install — a fresh tap is required.
  appState.current = "active";
  pending.resolve(handle);
  assert.equal(
    await startPromise,
    null,
    "backgrounded Start never installs after foreground return"
  );
  assert.equal(handle.endCalls, 1, "late room released exactly once");
});

test("fresh Start waits for an orphaned Start instead of opening a second room", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { handle: handle2 } = makeHandle();
  const appState = { current: "active" };
  let calls = 0;
  const { session, background } = makeSessionWithScheduler(
    () => (calls++ === 0 ? pending.promise : Promise.resolve(handle2)),
    scheduler,
    appState
  );
  const first = session.start();
  appState.current = "background";
  background();
  appState.current = "active";
  // The fresh tap is accepted (no single-flight rejection) but must not
  // open a room while the invalidated native Start is still unresolved.
  const secondPromise = session.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(calls, 1, "no second room while the orphaned Start is unresolved");
  pending.resolve(handle); // orphaned run settles late → disposed, never installs
  assert.equal(await first, null, "orphaned Start resolves to null");
  assert.equal(handle.endCalls, 1, "orphaned room released exactly once");
  assert.equal(await secondPromise, handle2, "fresh tap proceeds after the orphan settles");
  assert.equal(calls, 2, "exactly one new room, after orphan settlement");
  assert.equal(handle2.endCalls, 0, "fresh session untouched by the orphan");
});

test("orphaned completion does not clear a newer Start's watchdog", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { handle: handle2 } = makeHandle();
  const appState = { current: "active" };
  let calls = 0;
  const { session, background } = makeSessionWithScheduler(
    () => (calls++ === 0 ? pending.promise : Promise.resolve(handle2)),
    scheduler,
    appState
  );
  const first = session.start(); // arms the first timer
  appState.current = "background";
  background(); // clears it (cancels 1) and invalidates
  assert.equal(scheduler.cancels(), 1);
  appState.current = "active";
  const secondPromise = session.start(); // arms the second timer, then waits
  assert.equal(scheduler.schedules(), 2, "fresh tap arms its own 90-second window");
  pending.resolve(handle); // orphaned completion lands behind the newer timer
  assert.equal(await first, null);
  assert.equal(await secondPromise, handle2);
  assert.equal(scheduler.cancels(), 1, "orphan completion must not clear the newer timer");
  assert.ok(scheduler.pending(), "newer watchdog still armed");
});

test("watchdog expiry aborts a Start still waiting on an orphan", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>();
  const { handle } = makeHandle();
  const { handle: handle2 } = makeHandle();
  const appState = { current: "active" };
  let calls = 0;
  const { session, background } = makeSessionWithScheduler(
    () => (calls++ === 0 ? pending.promise : Promise.resolve(handle2)),
    scheduler,
    appState
  );
  const first = session.start();
  appState.current = "background";
  background();
  appState.current = "active";
  const secondPromise = session.start(); // waits on the orphan
  scheduler.trigger(); // the 90-second bound elapses while waiting
  pending.resolve(handle);
  assert.equal(await first, null);
  assert.equal(await secondPromise, null, "expired wait installs nothing; tap again");
  assert.equal(calls, 1, "expired wait never opened a room");
  assert.equal(handle.endCalls, 1, "orphaned room still released exactly once");
});

test("End returns while a Start is stalled and never installs it", async () => {
  const scheduler = makeScheduler();
  const pending = deferred<VoiceTestHandle>(); // never resolved: stalled fetch
  const { handle } = makeHandle();
  const { session } = makeSessionWithScheduler(() => pending.promise, scheduler);
  const startPromise = session.start();
  // Bounded microtask drain, no wall-clock: End must settle WITHOUT the
  // stalled Start settling first.
  let endSettled = false;
  const endPromise = session.end().then(() => {
    endSettled = true;
  });
  for (let i = 0; i < 50 && !endSettled; i++) await Promise.resolve();
  assert.ok(endSettled, "End settles without waiting for the stalled Start");
  await endPromise;
  // Late completion still cannot install.
  pending.resolve(handle);
  assert.equal(await startPromise, null, "late completion never installs");
  assert.equal(handle.endCalls, 1, "late room released exactly once");
});

test("failed previous End blocks Start and retains ownership", async () => {
  let endCalls = 0;
  let startCalls = 0;
  const oldHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      throw new Error("boom-prev-end");
    },
  };
  const newHandle = {
    async setMuted(_muted: boolean) {},
    async end() {},
  };
  const { session } = makeSession(async () => {
    startCalls += 1;
    return (startCalls === 1 ? oldHandle : newHandle) as never;
  });
  await session.start();
  await assert.rejects(session.start(), /boom-prev-end/);
  assert.equal(startCalls, 1, "no second room while previous may be live");
  assert.equal(endCalls, 1);
  await assert.rejects(session.end(), /boom-prev-end/);
});
