/**
 * Foreground-only session orchestration for the LiveKit audio spike.
 *
 * Framework-free (no React, no native imports): the screen owns rendering
 * and passes platform dependencies in, so this module is unit-checkable
 * with plain Node and never pulls LiveKit into the web bundle.
 *
 * Guarantees:
 * - A development-only 90-second watchdog (measured from the Start
 *   tap) invalidates a still-pending Start or ends a live session.
 *   The timer is cleared on End, failure, background, and disposal.
 *   It marks when cleanup is TRIGGERED, never a guaranteed release.
 * - End works while a Start is still pending: the pending start is
 *   invalidated and detached without waiting, so a stalled await never
 *   stalls End — and a fresh Start waits for the orphan to settle
 *   instead of opening a second room behind it (safety over liveness).
 *   Only the owning generation clears the watchdog, so an orphaned
 *   completion can never clear a newer Start's timer.
 * - A Start that is still pending when the screen exits (or the app
 *   backgrounds) is permanently invalidated and disposed as soon as it
 *   completes — the room and audio session are never leaked behind a
 *   dead screen, and a foreground return never revives it (fresh tap
 *   required). Invalidation never waits for a stalled await.
 * - The session handle is discarded only after cleanup settles; End
 *   works while Mute is pending, concurrent Ends share one teardown,
 *   and Mute/End failures stay visible instead of a false "ended".
 * - Every uncertain release keeps a recovery vehicle (the live
 *   handle, or a retained recovery handle once the live one is gone),
 *   so End always retries fresh: success clears the warning, failure
 *   keeps it retryable, and no second Start runs while the release is
 *   unresolved — whether the failure carried the mic-unconfirmed flag
 *   or not, since a rejected end() is never proven release.
 * - Genuine backgrounds end a live session (foreground-only test).
 *   Only the `background` state triggers this — never `inactive` — and
 *   only when a live handle exists, so the Android permission dialog
 *   during a pending Start can never falsely end the session.
 */
import type { VoiceTestHandle, VoiceTestStatus } from "./voice";

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

export class VoiceTestSession {
  private handle: VoiceTestHandle | null = null;
  /**
   * Retained recovery vehicle for an unconfirmed mic release. Set on
   * every successful Start alongside the live handle and deliberately
   * NOT cleared by a healthy End: a mic-off failure can land afterwards
   * (late toggle compensation), when no live handle exists to route
   * End to. Latest-wins single slot; a stale entry is a harmless no-op
   * through the native shared End promise. Cleared on dispose and
   * overwritten by the next Start.
   */
  private recoveryHandle: VoiceTestHandle | null = null;
  /**
   * True while a retained recovery room has unfinished cleanup: set when
   * an orphaned run's late disposal rejects for ANY reason — a rejected
   * end() is never proven release, whether or not it carried the
   * mic-unconfirmed flag. Gates fresh Starts (with a room-specific
   * message when the mic flag is absent) and routes End to the retained
   * handle. Cleared when a recovery End succeeds and on dispose.
   */
  private cleanupIncomplete = false;
  private generation = 0;
  private ending: Promise<void> | null = null;
  private starting: Promise<VoiceTestHandle | null> | null = null;
  private disposed = false;
  private lastStatus: VoiceTestStatus | null = null;
  private removeAppStateListener: (() => void) | null = null;
  private cancelWatchdog: (() => void) | null = null;
  /**
   * Detached runs of invalidated Starts. A fresh Start waits for every
   * orphan to settle before opening a room — their late completions can
   * only dispose (generation mismatch), never install. Entries remove
   * themselves on settlement; while one is outstanding, no second room
   * opens even if the orphan itself never settles (safety over liveness:
   * a stalled native await cannot be stopped from JS).
   */
  private readonly orphans = new Set<Promise<VoiceTestHandle | null>>();

  constructor(
    private readonly deps: VoiceTestSessionDeps,
    private readonly onStatus: (status: VoiceTestStatus) => void
  ) {
    this.removeAppStateListener = deps.addAppStateListener((state) =>
      this.onAppState(state)
    );
  }

  private get watchdogMs(): number {
    return this.deps.watchdogMs ?? VOICE_TEST_WATCHDOG_MS;
  }

  /** Arm the development safety bound, measured from the Start tap. */
  private armWatchdog(): void {
    this.clearWatchdog();
    const schedule =
      this.deps.scheduleWatchdog ??
      ((onFire: () => void, ms: number) => {
        const timer = setTimeout(onFire, ms);
        return () => clearTimeout(timer);
      });
    this.cancelWatchdog = schedule(() => this.onWatchdog(), this.watchdogMs);
  }

  private clearWatchdog(): void {
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
  private clearWatchdogIfCurrent(generation: number): void {
    if (generation === this.generation) this.clearWatchdog();
  }

  private onWatchdog(): void {
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

  /**
   * Permanently invalidate any pending Start WITHOUT waiting for it.
   * The orphaned run's own generation checks dispose its late completion
   * (or swallow its abort) once it settles, so it can never install —
   * even if conditions look favorable again by then (e.g. foreground
   * return). A stalled token fetch, connection, or mic publication must
   * not stall the caller: detachment is synchronous. A fresh Start does
   * NOT proceed immediately — it waits for the orphan to settle before
   * opening a room (see orphans); the run's finally-guard keeps a late
   * settlement from clearing a newer run's timer. The no-op catch attach
   * avoids an unhandled rejection if the orphaned run later rejects.
   *
   * Limit (verified against installed livekit-client 2.22.3): token
   * fetch, room connect, and mic publish expose no public cancellation —
   * connect only has timeouts for the unreachable-server case
   * (peerConnectionTimeout/websocketTimeout, 15 s) plus retries. A
   * stalled native await therefore cannot be stopped from here; it runs
   * to settlement and is disposed then. Mic release is attempted at
   * that point, never guaranteed.
   */
  private invalidatePendingStart(): void {
    this.generation += 1;
    const pending = this.starting;
    this.starting = null;
    if (pending) {
      // Tracked so a fresh Start waits for the orphan to settle instead
      // of opening a second room behind it; removed on settlement.
      // The no-op catch attach avoids an unhandled rejection if the
      // orphaned run later rejects.
      this.orphans.add(pending);
      const done = () => {
        this.orphans.delete(pending);
      };
      void pending.then(done, done);
    }
  }

  /** Start a session. Resolves to the live handle — or, when the Start
   *  itself failed with an unconfirmed mic release, to the recovery
   *  handle the displayed End retries (never treated as live: the last
   *  status already shows the failure). Resolves null when the start
   *  was overtaken and the late session was disposed. Terminal failures
   *  are reported through onStatus. Concurrent Starts are single-flight:
   *  the second rejects. A Start with no live handle is refused while
   *  the release is unconfirmed or a previous cleanup is incomplete —
   *  End first (re-checked after waiting on orphans, since their late
   *  cleanup can fail while this tap waits); a Start with a retained
   *  (possibly live) handle ends it first, retrying recovery inline.
   */
  async start(): Promise<VoiceTestHandle | null> {
    if (this.starting) throw new Error("Start already in progress.");
    if (!this.handle) {
      if (this.lastStatus?.micUnconfirmed === true) {
        throw new Error(
          "Microphone release unconfirmed; End to retry before starting again."
        );
      }
      if (this.cleanupIncomplete) {
        throw new Error(
          "Previous session cleanup did not complete; End to retry before starting again."
        );
      }
    }
    // Fresh tap, fresh 90-second window (a rejected single-flight Start
    // above never re-arms the first tap's timer).
    this.armWatchdog();
    const run = (async (): Promise<VoiceTestHandle | null> => {
    const generation = this.generation;
    if (this.orphans.size > 0) {
      // An invalidated native Start is still unresolved (or its late
      // cleanup unfinished): do not open another room behind it. Every
      // orphan settles to disposal (generation mismatch), never to an
      // install — then this run proceeds. If this run itself is
      // invalidated (or the watchdog fires) while waiting, the check
      // below ends it with nothing opened.
      await Promise.allSettled([...this.orphans]);
      if (
        this.disposed ||
        generation !== this.generation ||
        this.deps.getAppState() === "background"
      ) {
        this.clearWatchdogIfCurrent(generation);
        return null;
      }
      if (
        !this.handle &&
        (this.lastStatus?.micUnconfirmed === true || this.cleanupIncomplete)
      ) {
        // An orphan settled while this tap waited — and its late cleanup
        // left release uncertain (with or without the mic flag): do not
        // open a room behind it. The orphan's handle was retained for End
        // retry; this tap ends here like a refused Start.
        this.clearWatchdogIfCurrent(generation);
        throw new Error(
          this.lastStatus?.micUnconfirmed === true
            ? "Microphone release unconfirmed; End to retry before starting again."
            : "Previous session cleanup did not complete; End to retry before starting again."
        );
      }
    }
    const previous = this.handle;
    if (previous) {
      // End any previous session first so two rooms never run at once.
      // A failure here aborts the start and retains ownership: the old
      // session may still be live, and starting a second room would hide it.
      try {
        await previous.end();
      } catch (error) {
        this.clearWatchdogIfCurrent(generation);
        throw error;
      }
      if (this.handle === previous) this.handle = null;
    }
    if (
      this.disposed ||
      generation !== this.generation ||
      this.deps.getAppState() === "background"
    ) {
      // Overtaken while ending the previous session: do not open a room
      // behind a dead or backgrounded screen.
      this.clearWatchdogIfCurrent(generation);
      return null;
    }
    let handle: VoiceTestHandle;
    try {
      handle = await this.deps.startVoiceTest(
        (status) => {
          this.lastStatus = status;
          this.onStatus(status);
        },
        () =>
          this.disposed ||
          generation !== this.generation ||
          this.deps.getAppState() === "background"
      );
    } catch (error) {
      if (
        this.disposed ||
        generation !== this.generation ||
        this.deps.getAppState() === "background"
      ) {
        // Overtaken while pending: native cleanup already ran; the
        // rejection only ends the orphaned start, so swallow it.
        this.clearWatchdogIfCurrent(generation);
        return null;
      }
      this.clearWatchdogIfCurrent(generation);
      throw error;
    }
    if (
      this.disposed ||
      generation !== this.generation ||
      this.deps.getAppState() === "background"
    ) {
      // Overtaken while pending: release the room/audio session as soon
      // as it completes. A disposal failure is already reported through
      // onStatus by the handle itself — but when that release fails the
      // room is retained for End retry instead of being dropped with a
      // possibly-live mic, and incompleteness is recorded so no fresh
      // Start opens behind it: a rejected end() is never proven release,
      // whether or not it carried the mic-unconfirmed flag.
      try {
        await handle.end();
      } catch {
        this.recoveryHandle = handle;
        this.cleanupIncomplete = true;
      }
      this.clearWatchdogIfCurrent(generation);
      return null;
    }
    // Live handle installed (or the recovery vehicle of a failed Start,
    // whose unconfirmed last status the caller can see): the watchdog
    // stays armed so the 90-second bound still ends the session if
    // nobody else does.
    this.handle = handle;
    this.recoveryHandle = handle;
    return handle;
    })();
    this.starting = run;
    try {
      return await run;
    } finally {
      if (this.starting === run) this.starting = null;
    }
  }

  async setMuted(muted: boolean): Promise<void> {
    const handle = this.handle;
    if (!handle) {
      throw new Error("No active session to mute.");
    }
    await handle.setMuted(muted);
  }

  /** End the session. Usable while a Start is still pending: the
   *  pending start is invalidated and detached WITHOUT waiting for it —
   *  a stalled token fetch, connection, or mic publication must not
   *  stall this End. The orphaned run's own checks turn a late
   *  completion into a release (or a swallowed abort) instead of a room
   *  opened behind this End. Every unconfirmed release keeps a recovery
   *  vehicle — the live handle, or the retained recovery handle once the
   *  live one is gone and the last status still shows the release
   *  unconfirmed — so the displayed End always makes a fresh mic-off
   *  attempt: success clears the uncertainty, failure keeps the warning
   *  and stays retryable. A stale recovery entry after a healthy End is
   *  left alone, so repeat Ends stay no-ops. Safe to call concurrently
   *  and repeatedly: one teardown runs; the handle is dropped only on
   *  success so a failed cleanup can be retried, and a teardown failure
   *  is reported through onStatus (error, not "ended").
   */
  async end(): Promise<void> {
    this.clearWatchdog();
    this.invalidatePendingStart();
    // Prefer the live handle, else the retained recovery handle — but
    // only while release is actually uncertain: the last status shows
    // mic-unconfirmed, or a late cleanup failed without proving release.
    // A stale recovery entry after a healthy End must stay untouched so
    // repeat Ends remain no-ops (single teardown).
    const handle =
      this.handle ??
      (this.lastStatus?.micUnconfirmed === true || this.cleanupIncomplete
        ? this.recoveryHandle
        : null);
    if (!handle) return;
    if (!this.ending) {
      this.ending = handle.end().then(
        () => {
          // The live slot clears; the recovery slot deliberately lingers:
          // a mic-off failure can still land afterwards (late toggle
          // compensation), when no live handle exists to route End to.
          // A stale entry is a harmless no-op through the native shared
          // End promise, and Start gating reads the last status and the
          // incompleteness flag, never this slot. A resolved End proves
          // the release it attempted, so incompleteness clears here.
          if (this.handle === handle) this.handle = null;
          this.cleanupIncomplete = false;
          this.ending = null;
        },
        (error: unknown) => {
          this.ending = null;
          throw error;
        }
      );
    }
    return this.ending;
  }

  private onAppState(state: string): void {
    if (state !== "background") return;
    // Permanently invalidate any pending Start: even if the app returns
    // to the foreground before an await finishes, the orphaned run can
    // only dispose — a fresh tap is required to start again. Detached
    // without waiting (see invalidatePendingStart) so a stalled await
    // cannot stall this path either.
    this.clearWatchdog();
    this.invalidatePendingStart();
    if (!this.handle) return;
    const active =
      this.lastStatus === null ||
      this.lastStatus.state === "connected" ||
      this.lastStatus.state === "reconnecting";
    if (!active) return;
    // Foreground-only test: stop transmission when genuinely backgrounded.
    // Fire-and-forget with errors already surfaced through onStatus.
    void this.end().catch(() => undefined);
  }

  /** Screen exit: invalidate pending starts and release the session. */
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.generation += 1;
    this.recoveryHandle = null;
    this.cleanupIncomplete = false;
    this.clearWatchdog();
    if (this.removeAppStateListener) {
      this.removeAppStateListener();
      this.removeAppStateListener = null;
    }
    void this.end().catch(() => undefined);
  }
}
