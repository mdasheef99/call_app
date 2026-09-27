/**
 * Shared session scaffolding for the LiveKit audio spike: watchdog,
 * generation/invalidation, orphan waiting, and cross-session status
 * surfacing. Framework-free (no React, no native imports).
 *
 * `VoiceSessionBase` owns the fields and the invalidation machinery;
 * concrete Start/End behavior lives in subclasses so each module stays
 * small. Subclass methods run on the same instance (`this` preserved);
 * no awaits were added or removed in the move.
 */
import type { VoiceTestHandle, VoiceTestStatus } from "./voice";
import {
  notifySharedSettled,
  sharedEndings,
  sharedGateState,
  sharedListeners,
  sharedMutes,
  sharedOrphans,
} from "./voice-shared-gate";
import type { SharedGateListener } from "./voice-shared-gate";

/**
 * Development-only safety bound, measured from the Start tap: when it
 * fires, a still-pending Start is invalidated (its late room is
 * released) and a live session is ended. It marks the moment cleanup
 * is TRIGGERED — a failed cleanup still leaves the mic unconfirmed,
 * never a guaranteed release.
 */
export const VOICE_TEST_WATCHDOG_MS = 90_000;

export interface VoiceTestSessionDeps {
  startVoiceTest: (
    onStatus: (status: VoiceTestStatus) => void,
    shouldAbort?: () => boolean
  ) => Promise<VoiceTestHandle>;
  getAppState: () => string;
  addAppStateListener: (onChange: (state: string) => void) => () => void;
  /** Overridable for tests; defaults to the 90-second development bound. */
  watchdogMs?: number;
  /** Overridable for tests; defaults to real timers. Returns a cancel. */
  scheduleWatchdog?: (onFire: () => void, ms: number) => () => void;
}

export abstract class VoiceSessionBase {
  protected handle: VoiceTestHandle | null = null;
  /**
   * Retained recovery vehicle for an unconfirmed mic release. Set on
   * every successful Start alongside the live handle and deliberately
   * NOT cleared by a healthy End: a mic-off failure can land afterwards
   * (late toggle compensation), when no live handle exists to route
   * End to. Latest-wins single slot; a stale entry is a harmless no-op
   * through the native shared End promise. Cleared on dispose and
   * overwritten by the next Start.
   */
  protected recoveryHandle: VoiceTestHandle | null = null;
  /**
   * True while a retained recovery room has unfinished cleanup: set when
   * an orphaned run's late disposal rejects for ANY reason — a rejected
   * end() is never proven release, whether or not it carried the
   * mic-unconfirmed flag. Gates fresh Starts (with a room-specific
   * message when the mic flag is absent) and routes End to the retained
   * handle. Cleared when a recovery End succeeds and on dispose.
   */
  protected cleanupIncomplete = false;
  protected generation = 0;
  protected ending: Promise<void> | null = null;
  protected starting: Promise<VoiceTestHandle | null> | null = null;
  protected disposed = false;
  protected lastStatus: VoiceTestStatus | null = null;
  protected removeAppStateListener: (() => void) | null = null;
  protected cancelWatchdog: (() => void) | null = null;
  /**
   * Detached runs of invalidated Starts. A fresh Start waits for every
   * orphan to settle before opening a room — their late completions can
   * only dispose (generation mismatch), never install. Entries remove
   * themselves on settlement; while one is outstanding, no second room
   * opens even if the orphan itself never settles (safety over liveness:
   * a stalled native await cannot be stopped from JS). Instance set is
   * mirrored into the cross-session shared gate so a remounted screen
   * (dispose + new session) waits too.
   */
  protected readonly orphans = new Set<Promise<VoiceTestHandle | null>>();
  /**
   * Waiters notified on every generation bump (End/watchdog/background/
   * dispose invalidation). Lets a Start parked on `orphans` abort
   * promptly instead of hanging when the orphan never settles — the
   * aborted tap still never opens a room.
   */
  protected readonly generationWaiters = new Set<() => void>();
  protected readonly sharedEntry: SharedGateListener = {
    owner: this,
    notify: () => this.onSharedSettled(),
  };

  constructor(
    protected readonly deps: VoiceTestSessionDeps,
    protected readonly onStatus: (status: VoiceTestStatus) => void
  ) {
    this.removeAppStateListener = deps.addAppStateListener((state) =>
      this.onAppState(state)
    );
    // A remounted screen must reflect an in-flight or failed release even
    // before its first Start tap: pending (End shown, Start hidden) while
    // held, actionable error once failed. A clear gate leaves this session
    // untouched so a fresh mount keeps the screen's idle initial status.
    sharedListeners.add(this.sharedEntry);
    if (sharedGateState.micUnconfirmed || sharedGateState.cleanupIncomplete) {
      this.surfaceSharedBlock();
    } else if (sharedOrphans.size > 0 || sharedEndings.size > 0 || sharedMutes.size > 0) {
      const waiting: VoiceTestStatus = {
        state: "requesting",
        muted: false,
        participantCount: 0,
        errorMessage: "Waiting for previous session cleanup.",
      };
      this.lastStatus = waiting;
      this.onStatus(waiting);
    }
  }

  protected get watchdogMs(): number {
    return this.deps.watchdogMs ?? VOICE_TEST_WATCHDOG_MS;
  }

  /** Arm the development safety bound, measured from the Start tap. */
  protected armWatchdog(): void {
    this.clearWatchdog();
    const schedule =
      this.deps.scheduleWatchdog ??
      ((onFire: () => void, ms: number) => {
        const timer = setTimeout(onFire, ms);
        return () => clearTimeout(timer);
      });
    this.cancelWatchdog = schedule(() => this.onWatchdog(), this.watchdogMs);
  }

  protected clearWatchdog(): void {
    if (this.cancelWatchdog) {
      this.cancelWatchdog();
      this.cancelWatchdog = null;
    }
  }

  /**
   * Clear the watchdog only for the generation that armed it: a
   * late-settling orphaned run must never clear a newer Start's timer.
   * External invalidators (End/background/dispose) clear directly —
   * they bump the generation first, so the timer is theirs to drop.
   */
  protected clearWatchdogIfCurrent(generation: number): void {
    if (generation === this.generation) this.clearWatchdog();
  }

  protected onWatchdog(): void {
    this.cancelWatchdog = null;
    if (this.disposed) return;
    if (this.handle) {
      // Live past the bound: trigger End (errors surface via onStatus).
      void this.end().catch(() => undefined);
      return;
    }
    if (this.starting) {
      // Still pending: invalidate so the late result cannot open a room,
      // without waiting for it. The run itself releases the late handle
      // (or swallows the abort) once it settles.
      this.invalidatePendingStart();
    }
  }

  /** Implemented by the concrete session (End/teardown lives there). */
  abstract end(): Promise<void>;
  /** Implemented by the concrete session (foreground-only background rule). */
  protected abstract onAppState(state: string): void;

  /**
   * Bump the generation and wake every waiter parked on `orphans`: the
   * invalidated run (if any) becomes an orphan, and any tap already
   * waiting on orphans aborts promptly with nothing opened.
   */
  protected bumpGeneration(): void {
    this.generation += 1;
    const waiters = [...this.generationWaiters];
    this.generationWaiters.clear();
    for (const wake of waiters) wake();
  }

  /**
   * Wait until every orphan, in-flight release, and in-flight mute settles
   * so no second room opens behind one. Includes cross-session orphans
   * from disposed screens, shared live-End teardowns, and old in-flight
   * mutes. Resolves true when the coast is clear (caller still re-checks
   * generation, disposal, app state, and the release gates). Resolves
   * false when this run itself is invalidated while waiting
   * (End/watchdog/background/dispose) — even if an orphan never
   * settles — so the tap ends promptly with nothing opened.
   */
  protected waitForOrphans(generation: number): Promise<boolean> {
    if (this.orphans.size === 0 && sharedOrphans.size === 0 && sharedEndings.size === 0 && sharedMutes.size === 0) {
      return Promise.resolve(true);
    }
    if (generation !== this.generation || this.disposed) {
      return Promise.resolve(false);
    }
    return new Promise<boolean>((resolve) => {
      let done = false;
      const finish = (value: boolean) => {
        if (done) return;
        done = true;
        this.generationWaiters.delete(onBump);
        resolve(value);
      };
      const onBump = () => finish(false);
      this.generationWaiters.add(onBump);
      void Promise.allSettled([
        ...new Set([...this.orphans, ...sharedOrphans]),
        ...sharedEndings,
        ...sharedMutes,
      ]).then(() => finish(true));
    });
  }

  /**
   * Permanently invalidate any pending Start WITHOUT waiting for it.
   * The orphaned run's own generation checks dispose its late completion
   * (or swallow its abort) once it settles, so it can never install —
   * even if conditions look favorable again by then (e.g. foreground
   * return). A stalled token fetch, connection, or mic publication must
   * not stall the caller: detachment is synchronous. A fresh Start does
   * NOT proceed immediately — it waits for the orphan to settle before
   * opening a room (see orphans, waitForOrphans); the run's finally-guard
   * keeps a late settlement from clearing a newer run's timer. The no-op
   * catch attach avoids an unhandled rejection if the orphaned run later
   * rejects.
   *
   * Limit (verified against installed livekit-client 2.22.3): token
   * fetch, room connect, and mic publish expose no public cancellation —
   * connect only has timeouts for the unreachable-server case
   * (peerConnectionTimeout/websocketTimeout, 15 s) plus retries. A
   * stalled native await therefore cannot be stopped from here; it runs
   * to settlement and is disposed then. Mic release is attempted at
   * that point, never guaranteed.
   */
  protected invalidatePendingStart(): void {
    this.bumpGeneration();
    const pending = this.starting;
    this.starting = null;
    if (pending) {
      // Tracked so a fresh Start waits for the orphan to settle instead
      // of opening a second room behind it; removed on settlement.
      // Mirrored into the cross-session gate so a remounted screen waits
      // too. The no-op catch attach avoids an unhandled rejection if the
      // orphaned run later rejects.
      this.orphans.add(pending);
      sharedOrphans.add(pending);
      const done = () => {
        this.orphans.delete(pending);
        sharedOrphans.delete(pending);
        notifySharedSettled();
      };
      void pending.then(done, done);
    }
  }

  /**
   * Surface a shared fail-closed block on this (remounted) session so the
   * new screen shows a usable End retry instead of stale idle/waiting.
   * Only emits when the block comes from another screen (shared flags);
   * own terminals were already reported through this session's onStatus.
   */
  protected surfaceSharedBlock(): void {
    if (!sharedGateState.micUnconfirmed && !sharedGateState.cleanupIncomplete) return;
    const mic = sharedGateState.micUnconfirmed;
    const blocked: VoiceTestStatus = {
      state: "error",
      muted: false,
      participantCount: 0,
      errorMessage: mic
        ? "Microphone release unconfirmed; End to retry before starting again."
        : "Previous session cleanup did not complete; End to retry before starting again.",
      ...(mic ? { micUnconfirmed: true } : {}),
      cleanupFailed: true,
    };
    this.lastStatus = blocked;
    this.onStatus(blocked);
  }

  /**
   * Shared release outcome for a live remounted screen (no Start tapped,
   * or a wait already aborted): surface the failure as an actionable
   * error, or settle back to startable idle once the gate clears. Never
   * touches a disposed screen (unsubscribed), a live handle (newer active
   * status wins), or a pending Start (its wait path owns the outcome).
   * Never starts rooms or retries releases by itself.
   */
  protected onSharedSettled(): void {
    if (this.disposed || this.handle || this.starting) return;
    if (sharedGateState.micUnconfirmed || sharedGateState.cleanupIncomplete) {
      const st = this.lastStatus;
      const alreadyBlocked =
        st !== null &&
        st.state === "error" &&
        st.cleanupFailed === true &&
        (st.micUnconfirmed === true) === sharedGateState.micUnconfirmed;
      if (!alreadyBlocked) this.surfaceSharedBlock();
      return;
    }
    const st = this.lastStatus;
    if (
      st !== null &&
      sharedOrphans.size === 0 &&
      sharedEndings.size === 0 &&
      sharedMutes.size === 0 &&
      (st.errorMessage === "Waiting for previous session cleanup." ||
        (st.state === "error" && st.cleanupFailed === true))
    ) {
      const idle: VoiceTestStatus = {
        state: "idle",
        muted: false,
        participantCount: 0,
        errorMessage: null,
      };
      this.lastStatus = idle;
      this.onStatus(idle);
    }
  }
}
