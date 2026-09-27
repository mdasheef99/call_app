/**
 * Cross-session ownership: remounting the Audio Test screen (dispose +
 * new session) must not open a second room behind a still-pending native
 * Start or a held live End. P02 forbids duplicate active sessions; a
 * never-settling await must never open a room or imply mic release, End
 * stays non-blocking, and a failed release stays retryable with truthful
 * status on the remounted screen.
 */
import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";
import { VoiceTestSession, resetSharedVoiceGateForTests } from "../lib/voice-session";
import { describeMicrophone } from "../lib/voice";
import type { VoiceTestHandle, VoiceTestStatus } from "../lib/voice";

beforeEach(() => {
  resetSharedVoiceGateForTests();
});

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
  const handle: VoiceTestHandle & { endCalls: number } = {
    endCalls: 0,
    async setMuted(_muted: boolean) {},
    async end() {
      handle.endCalls += 1;
    },
  };
  return { handle };
}

function makeSession(
  startVoiceTest: (onStatus: (status: VoiceTestStatus) => void) => Promise<VoiceTestHandle>,
  onStatus: (status: VoiceTestStatus) => void = () => undefined
) {
  return new VoiceTestSession(
    {
      startVoiceTest,
      getAppState: () => "active",
      addAppStateListener: () => () => undefined,
    },
    onStatus
  );
}

test("remount waits for the disposed orphan settlement and cleanup before opening a second room", async () => {
  let calls = 0;
  const pending = deferred<VoiceTestHandle>();
  const { handle: orphanHandle } = makeHandle();
  const { handle: freshHandle } = makeHandle();
  const session1Statuses: VoiceTestStatus[] = [];
  const session2Statuses: VoiceTestStatus[] = [];

  const session1 = makeSession(
    () => {
      calls += 1;
      if (calls === 1) return pending.promise;
      return Promise.resolve(freshHandle);
    },
    (s) => {
      session1Statuses.push(s);
    }
  );
  const first = session1.start();
  for (let i = 0; i < 20; i++) await Promise.resolve();
  assert.equal(calls, 1, "first native attempt started");

  // Remount: dispose the screen/session while the native connect is held.
  session1.dispose();

  const session2 = makeSession(
    () => {
      calls += 1;
      return Promise.resolve(freshHandle);
    },
    (s) => {
      session2Statuses.push(s);
    }
  );
  const secondPromise = session2.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(calls, 1, "no second room while the first attempt is unresolved");

  // First attempt settles late: its room is disposed (cleanup), then the
  // remounted session may open exactly one new room.
  pending.resolve(orphanHandle);
  assert.equal(await first, null, "disposed Start installs nothing");
  assert.equal(orphanHandle.endCalls, 1, "orphaned room released exactly once");
  assert.equal(await secondPromise, freshHandle, "fresh tap proceeds after orphan cleanup");
  assert.equal(calls, 2, "exactly one new room, after orphan settlement");
  session2.dispose();
  void session1Statuses;
  void session2Statuses;
});

test("cross-session failed mic release stays gated until shared End recovers", async () => {
  let calls = 0;
  const pending = deferred<VoiceTestHandle>();
  let endCalls = 0;
  let endFails = true;
  const orphanHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      if (endFails) throw new Error("Microphone release unconfirmed: boom");
    },
  };
  const { handle: freshHandle } = makeHandle();

  const session1 = makeSession(() => {
    calls += 1;
    return pending.promise;
  });
  const first = session1.start();
  for (let i = 0; i < 20; i++) await Promise.resolve();
  assert.equal(calls, 1);
  session1.dispose();

  const statuses: VoiceTestStatus[] = [];
  const session2 = makeSession(
    () => {
      calls += 1;
      return Promise.resolve(freshHandle);
    },
    (s) => {
      statuses.push(s);
    }
  );
  const secondPromise = session2.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(calls, 1, "no second room while the first attempt is unresolved");

  pending.resolve(orphanHandle);
  assert.equal(await first, null);
  assert.equal(endCalls, 1, "orphaned room release attempted once");
  await assert.rejects(secondPromise, /unconfirmed/i);
  assert.equal(calls, 1, "failed cross-session cleanup opens no room");

  endFails = false;
  await session2.end();
  assert.equal(endCalls, 2, "shared End retried the failed release");
  await session2.start();
  assert.equal(calls, 2, "Start allowed again after confirmed recovery");
  session2.dispose();
});

test("cross-session failed cleanup without mic flag stays gated until shared End recovers", async () => {
  let calls = 0;
  const pending = deferred<VoiceTestHandle>();
  let endCalls = 0;
  let endFails = true;
  const orphanHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      if (endFails) throw new Error("boom-disconnect");
    },
  };
  const { handle: freshHandle } = makeHandle();

  const session1 = makeSession(() => {
    calls += 1;
    return pending.promise;
  });
  const first = session1.start();
  for (let i = 0; i < 20; i++) await Promise.resolve();
  assert.equal(calls, 1);
  session1.dispose();

  const session2 = makeSession(() => {
    calls += 1;
    return Promise.resolve(freshHandle);
  });
  const secondPromise = session2.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(calls, 1, "no second room while the first attempt is unresolved");

  pending.resolve(orphanHandle);
  assert.equal(await first, null);
  assert.equal(endCalls, 1);
  await assert.rejects(secondPromise, /did not complete/i);
  assert.equal(calls, 1, "uncertain cross-session release opens no room");

  endFails = false;
  await session2.end();
  assert.equal(endCalls, 2, "shared End retried the failed cleanup");
  await session2.start();
  assert.equal(calls, 2, "Start allowed again after completed cleanup");
  session2.dispose();
});

test("never-settling orphan never opens a second room, claims no mic release, End stays non-blocking", async () => {
  let calls = 0;
  const never = deferred<VoiceTestHandle>(); // never resolved
  const statuses: VoiceTestStatus[] = [];

  const session1 = makeSession(() => {
    calls += 1;
    return never.promise;
  });
  const first = session1.start();
  for (let i = 0; i < 20; i++) await Promise.resolve();
  assert.equal(calls, 1);
  session1.dispose();

  const session2 = makeSession(
    () => {
      calls += 1;
      const { handle } = makeHandle();
      return Promise.resolve(handle);
    },
    (s) => {
      statuses.push(s);
    }
  );
  const secondPromise = session2.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(calls, 1, "never-settling await opens no second room");
  assert.ok(
    statuses.some((s) => s.state === "requesting"),
    "waiting tap reports pending while the orphan is unresolved"
  );
  assert.ok(
    statuses.every((s) => !s.micUnconfirmed && !s.cleanupFailed),
    "no release implied while the mic was never published"
  );

  // End must abort the parked wait promptly without the orphan settling.
  let endSettled = false;
  const endPromise = session2.end().then(() => {
    endSettled = true;
  });
  for (let i = 0; i < 50 && !endSettled; i++) await Promise.resolve();
  assert.ok(endSettled, "End settles without waiting for the stalled Start");
  await endPromise;
  assert.equal(await secondPromise, null, "aborted wait installs nothing");
  assert.equal(calls, 1, "aborted wait never opened a room");
  assert.ok(
    (statuses[statuses.length - 1]?.micUnconfirmed ?? false) === false &&
      (statuses[statuses.length - 1]?.cleanupFailed ?? false) === false,
    "abort claims no mic release"
  );
  session2.dispose();
  void first;
});

test("remount during held live End waits until release succeeds before opening a second room", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCalls = 0;
  const liveHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      await release.promise;
    },
  };
  const { handle: freshHandle } = makeHandle();

  const session1 = makeSession(async (onStatus) => {
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandle;
  });
  await session1.start();
  assert.equal(startCalls, 1);

  const endPromise = session1.end();
  for (let i = 0; i < 50 && endCalls < 1; i++) await Promise.resolve();
  assert.equal(endCalls, 1, "live End entered and held");
  session1.dispose();

  const session2 = makeSession(async () => {
    startCalls += 1;
    return freshHandle;
  });
  const secondPromise = session2.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "no second room while the live End is held");

  release.resolve();
  await endPromise;
  assert.equal(await secondPromise, freshHandle, "fresh Start proceeds after live release succeeds");
  assert.equal(startCalls, 2, "exactly one new room after release");
  session2.dispose();
});

test("remount during held live End failure stays gated until shared End recovers", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCalls = 0;
  let endFails = true;
  const liveHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      await release.promise;
      if (endFails) throw new Error("boom-disconnect");
    },
  };
  const { handle: freshHandle } = makeHandle();

  const session1 = makeSession(async (onStatus) => {
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandle;
  });
  await session1.start();
  const endPromise = session1.end();
  for (let i = 0; i < 50 && endCalls < 1; i++) await Promise.resolve();
  assert.equal(endCalls, 1);
  session1.dispose();

  const session2 = makeSession(async () => {
    startCalls += 1;
    return freshHandle;
  });
  const secondPromise = session2.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "no second room while the live End is held");

  release.resolve();
  await assert.rejects(endPromise, /boom-disconnect/);
  await assert.rejects(secondPromise, /did not complete/i);
  assert.equal(startCalls, 1, "failed live release opens no second room");

  endFails = false;
  await session2.end();
  assert.equal(endCalls, 2, "remounted End retried the failed live release");
  await session2.start();
  assert.equal(startCalls, 2, "Start allowed again after confirmed recovery");
  session2.dispose();
});

test("remounted screen shows truthful status through failed cleanup into successful retry", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCalls = 0;
  let endFails = true;
  const liveHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      await release.promise;
      if (endFails) throw new Error("Microphone release unconfirmed: boom");
    },
  };
  const { handle: freshHandle } = makeHandle();

  const session1 = makeSession(async (onStatus) => {
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandle;
  });
  await session1.start();
  const endPromise = session1.end();
  for (let i = 0; i < 50 && endCalls < 1; i++) await Promise.resolve();
  session1.dispose();

  const statuses: VoiceTestStatus[] = [];
  const session2 = makeSession(
    async () => {
      startCalls += 1;
      return freshHandle;
    },
    (s) => {
      statuses.push(s);
    }
  );
  const secondPromise = session2.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "no second room while the live End is held");
  assert.ok(
    statuses.some((s) => s.state === "requesting"),
    "waiting tap reports pending while the live End is held"
  );
  assert.ok(
    statuses.every((s) => !s.micUnconfirmed && !s.cleanupFailed),
    "waiting claims no release"
  );

  release.resolve();
  await assert.rejects(endPromise, /unconfirmed/i);
  await assert.rejects(secondPromise, /unconfirmed/i);
  assert.equal(startCalls, 1, "failed live release opens no second room");

  const failed = statuses[statuses.length - 1];
  assert.equal(failed?.state, "error", "failed cleanup surfaces error on the new session");
  assert.equal(failed?.micUnconfirmed, true, "mic release shown unconfirmed, never off");
  assert.equal(failed?.cleanupFailed, true, "End retry advertised");
  await assert.rejects(session2.start(), /unconfirmed/i, "Start unusable while release uncertain");
  assert.equal(startCalls, 1, "gated Start still opens no room");

  endFails = false;
  await session2.end();
  const recovered = statuses[statuses.length - 1];
  assert.equal(recovered?.state, "ended", "successful retry lands ended on the new session");
  assert.ok(!recovered?.micUnconfirmed && !recovered?.cleanupFailed, "retry clears the warning");

  await session2.start();
  assert.equal(startCalls, 2, "Start usable again after confirmed recovery");
  session2.dispose();
});

test("remounted screen without Start shows release-in-progress while live End held, then startable after success", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCalls = 0;
  const liveHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      await release.promise;
    },
  };
  const { handle: freshHandle } = makeHandle();

  const sessionA = makeSession(async (onStatus) => {
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandle;
  });
  await sessionA.start();
  const endPromise = sessionA.end();
  for (let i = 0; i < 50 && endCalls < 1; i++) await Promise.resolve();
  assert.equal(endCalls, 1, "live End entered and held");
  sessionA.dispose();

  // B mounts but never taps Start: it must not show idle/off-startable.
  const statusesB: VoiceTestStatus[] = [];
  const sessionB = makeSession(
    async () => {
      startCalls += 1;
      return freshHandle;
    },
    (s) => {
      statusesB.push(s);
    }
  );
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "mounting without Start opens no room");
  const pending = statusesB[statusesB.length - 1];
  assert.equal(pending?.state, "requesting", "B shows release-in-progress, not idle/off");
  assert.equal(pending?.errorMessage, "Waiting for previous session cleanup.");
  assert.ok(!pending?.micUnconfirmed && !pending?.cleanupFailed, "in-progress claims no completed release");

  // End stays non-blocking while the release is held: prompt no-op, no room.
  let endSettled = false;
  const endNoop = sessionB.end().then(() => {
    endSettled = true;
  });
  for (let i = 0; i < 50 && !endSettled; i++) await Promise.resolve();
  assert.ok(endSettled, "End settles promptly while the old release is held");
  await endNoop;
  assert.equal(startCalls, 1, "End while waiting opens no room");

  release.resolve();
  await endPromise;
  for (let i = 0; i < 50; i++) await Promise.resolve();
  const ready = statusesB[statusesB.length - 1];
  assert.equal(ready?.state, "idle", "successful release makes B startable");
  assert.ok(!ready?.micUnconfirmed && !ready?.cleanupFailed, "release proven: mic off is truthful now");

  await sessionB.start();
  assert.equal(startCalls, 2, "exactly one new room after release");
  sessionB.dispose();
});

test("remounted screen without Start shows actionable mic failure and recovers via End", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCalls = 0;
  let endFails = true;
  const liveHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      await release.promise;
      if (endFails) throw new Error("Microphone release unconfirmed: boom");
    },
  };
  const { handle: freshHandle } = makeHandle();

  const sessionA = makeSession(async (onStatus) => {
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandle;
  });
  await sessionA.start();
  const endPromise = sessionA.end();
  for (let i = 0; i < 50 && endCalls < 1; i++) await Promise.resolve();
  sessionA.dispose();

  const statusesB: VoiceTestStatus[] = [];
  const sessionB = makeSession(
    async () => {
      startCalls += 1;
      return freshHandle;
    },
    (s) => {
      statusesB.push(s);
    }
  );
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "mounting without Start opens no room");

  release.resolve();
  await assert.rejects(endPromise, /unconfirmed/i);
  for (let i = 0; i < 50; i++) await Promise.resolve();
  const failed = statusesB[statusesB.length - 1];
  assert.equal(failed?.state, "error", "failed release surfaces error on B without any Start tap");
  assert.equal(failed?.micUnconfirmed, true, "mic release shown unconfirmed, never off");
  assert.equal(failed?.cleanupFailed, true, "End retry advertised");
  await assert.rejects(sessionB.start(), /unconfirmed/i, "Start unusable while release uncertain");
  assert.equal(startCalls, 1, "gated Start opens no room");

  endFails = false;
  await sessionB.end();
  const recovered = statusesB[statusesB.length - 1];
  assert.equal(recovered?.state, "ended", "successful retry lands ended on B");
  assert.ok(!recovered?.micUnconfirmed && !recovered?.cleanupFailed, "retry clears the warning");

  await sessionB.start();
  assert.equal(startCalls, 2, "Start usable again after confirmed recovery");
  sessionB.dispose();
});

test("aborted wait still receives late cleanup failure; failed retry stays gated, success clears", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCalls = 0;
  let endFails = true;
  const liveHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      await release.promise;
      if (endFails) throw new Error("boom-disconnect");
    },
  };
  const { handle: freshHandle } = makeHandle();

  const sessionA = makeSession(async (onStatus) => {
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandle;
  });
  await sessionA.start();
  const endPromise = sessionA.end();
  for (let i = 0; i < 50 && endCalls < 1; i++) await Promise.resolve();
  sessionA.dispose();

  const statusesB: VoiceTestStatus[] = [];
  const sessionB = makeSession(
    async () => {
      startCalls += 1;
      return freshHandle;
    },
    (s) => {
      statusesB.push(s);
    }
  );
  const secondPromise = sessionB.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "no second room while the live End is held");

  // B aborts its wait before A settles: prompt, nothing opened.
  let abortSettled = false;
  const abortEnd = sessionB.end().then(() => {
    abortSettled = true;
  });
  for (let i = 0; i < 50 && !abortSettled; i++) await Promise.resolve();
  assert.ok(abortSettled, "End aborts the parked wait promptly");
  await abortEnd;
  assert.equal(await secondPromise, null, "aborted wait installs nothing");
  assert.equal(startCalls, 1, "aborted wait never opened a room");

  // A's End fails later: B must still receive the actionable failure.
  release.resolve();
  await assert.rejects(endPromise, /boom-disconnect/);
  for (let i = 0; i < 50; i++) await Promise.resolve();
  const failed = statusesB[statusesB.length - 1];
  assert.equal(failed?.state, "error", "late failure still reaches the aborted screen");
  assert.equal(failed?.cleanupFailed, true, "End retry advertised after abort");
  assert.ok(!failed?.micUnconfirmed, "no mic flag: mic-off succeeded, disconnect did not");
  await assert.rejects(sessionB.start(), /did not complete/i, "Start stays gated after abort + failure");
  assert.equal(startCalls, 1, "gated Start opens no room");

  // A failed retry remains visible and gated.
  await assert.rejects(sessionB.end(), /boom-disconnect/);
  const stillFailed = statusesB[statusesB.length - 1];
  assert.equal(stillFailed?.state, "error", "failed retry remains visible");
  assert.equal(stillFailed?.cleanupFailed, true, "retry stays advertised");
  await assert.rejects(sessionB.start(), /did not complete/i);
  assert.equal(startCalls, 1, "still gated after failed retry");

  // A successful retry clears it and Start works.
  endFails = false;
  await sessionB.end();
  const recovered = statusesB[statusesB.length - 1];
  assert.equal(recovered?.state, "ended", "successful retry lands ended");
  assert.ok(!recovered?.micUnconfirmed && !recovered?.cleanupFailed, "retry clears the warning");
  await sessionB.start();
  assert.equal(startCalls, 2, "Start usable again after confirmed recovery");
  sessionB.dispose();
});

test("late result from a disposed screen cannot overwrite newer active status or touch a disposed screen", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCallsA = 0;
  let pushToDeadA!: (status: VoiceTestStatus) => void;
  const liveHandleA: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCallsA += 1;
      await release.promise;
    },
  };
  const liveHandleB: VoiceTestHandle & { endCalls: number } = {
    endCalls: 0,
    async setMuted(_muted: boolean) {},
    async end() {
      liveHandleB.endCalls += 1;
    },
  };

  const sessionA = makeSession(async (onStatus) => {
    pushToDeadA = onStatus;
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandleA;
  });
  await sessionA.start();
  const endPromiseA = sessionA.end();
  for (let i = 0; i < 50 && endCallsA < 1; i++) await Promise.resolve();
  sessionA.dispose();

  const statusesB: VoiceTestStatus[] = [];
  const sessionB = makeSession(
    async (onStatus) => {
      startCalls += 1;
      onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
      return liveHandleB;
    },
    (s) => {
      statusesB.push(s);
    }
  );
  const startB = sessionB.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "B waits while the old release is held");
  release.resolve();
  await endPromiseA;
  assert.equal(await startB, liveHandleB, "B connects after the old release succeeds");
  assert.equal(startCalls, 2);
  await sessionB.setMuted(true);
  const connectedB = statusesB[statusesB.length - 1];
  assert.equal(connectedB?.state, "connected", "B holds newer active status");
  const bLengthBeforeStale = statusesB.length;

  // Stale late emission on the dead screen must not reach live B.
  pushToDeadA({
    state: "error",
    muted: false,
    participantCount: 0,
    errorMessage: "Microphone release unconfirmed: stale-boom",
    micUnconfirmed: true,
    cleanupFailed: true,
  });
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(statusesB.length, bLengthBeforeStale, "stale dead-screen result adds nothing to B");
  const stillB = statusesB[statusesB.length - 1];
  assert.equal(stillB?.state, "connected", "newer active status stands");
  assert.ok(!stillB?.micUnconfirmed && !stillB?.cleanupFailed, "no stale flags leak into B");
  await sessionB.setMuted(false);

  // A disposed screen receives nothing further either.
  const statusesD: VoiceTestStatus[] = [];
  const sessionD = makeSession(
    async () => {
      startCalls += 1;
      const { handle } = makeHandle();
      return handle;
    },
    (s) => {
      statusesD.push(s);
    }
  );
  sessionD.dispose();
  const dLength = statusesD.length;
  pushToDeadA({
    state: "error",
    muted: false,
    participantCount: 0,
    errorMessage: "Microphone release unconfirmed: stale-boom-again",
    micUnconfirmed: true,
    cleanupFailed: true,
  });
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(statusesD.length, dLength, "disposed screen gets no late updates");
  assert.equal(startCalls, 2, "stale results open no rooms");

  await sessionB.end();
  sessionB.dispose();
});

test("aborted wait keeps conservative Waiting display while the live End is held", async () => {
  let startCalls = 0;
  const release = deferred<void>();
  let endCalls = 0;
  const liveHandle: VoiceTestHandle = {
    async setMuted(_muted: boolean) {},
    async end() {
      endCalls += 1;
      await release.promise;
    },
  };
  const { handle: freshHandle } = makeHandle();

  const sessionA = makeSession(async (onStatus) => {
    startCalls += 1;
    onStatus({ state: "connected", muted: false, participantCount: 1, errorMessage: null });
    return liveHandle;
  });
  await sessionA.start();
  assert.equal(startCalls, 1);
  const endPromise = sessionA.end();
  for (let i = 0; i < 50 && endCalls < 1; i++) await Promise.resolve();
  assert.equal(endCalls, 1, "live End entered and held");
  sessionA.dispose();

  const statusesB: VoiceTestStatus[] = [];
  const sessionB = makeSession(
    async () => {
      startCalls += 1;
      return freshHandle;
    },
    (s) => {
      statusesB.push(s);
    }
  );
  const secondPromise = sessionB.start();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  assert.equal(startCalls, 1, "no second room while the live End is held");

  // B aborts its wait while A's End remains held: prompt, nothing opened,
  // and the display must stay conservative until every shared release
  // settles — still release-in-progress, never a startable-looking
  // terminal and never idle while an End remains pending.
  await sessionB.end();
  assert.equal(await secondPromise, null, "aborted wait installs nothing");
  assert.equal(startCalls, 1, "aborted wait never opened a room");
  for (let i = 0; i < 50; i++) await Promise.resolve();
  const held = statusesB[statusesB.length - 1];
  assert.ok(held, "B displayed something after abort");
  assert.equal(held.state, "requesting", "display stays release-in-progress while End held");
  assert.equal(held.errorMessage, "Waiting for previous session cleanup.");
  assert.ok(!held.micUnconfirmed && !held.cleanupFailed, "no completed release implied");
  assert.equal(describeMicrophone(held), "off", "mic label matches waiting display");

  // Once every shared release settles, B becomes honestly startable.
  release.resolve();
  await endPromise;
  for (let i = 0; i < 50; i++) await Promise.resolve();
  const ready = statusesB[statusesB.length - 1];
  assert.ok(ready, "B displayed something after release");
  assert.equal(ready.state, "idle", "settled release makes B startable");
  assert.equal(describeMicrophone(ready), "off", "mic off truthful only after proven release");

  await sessionB.start();
  assert.equal(startCalls, 2, "exactly one new room after release");
  sessionB.dispose();
});
