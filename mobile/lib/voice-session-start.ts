/**
 * Start path for the LiveKit audio spike session.
 *
 * Intermediate subclass so each module stays small. Runs on the same
 * instance (`this` preserved from `VoiceSessionBase`); the Start run,
 * orphan wait, abort race, and watchdog-ownership order are verbatim —
 * no awaits added or removed, no status text changed.
 */
import type { VoiceTestHandle, VoiceTestStatus } from "./voice";
import {
  sharedEndings,
  sharedGateState,
  sharedOrphans,
} from "./voice-shared-gate";
import { VoiceSessionBase } from "./voice-session-base";

export abstract class VoiceSessionStarter extends VoiceSessionBase {
  /** Start a session. Resolves to the live handle — or, when the Start
   *  itself failed with an unconfirmed mic release, to the recovery
   *  handle the displayed End retries (never treated as live: the last
   *  status already shows the failure). Resolves null when the start
   *  was overtaken and the late session was disposed, or when a wait
   *  on unresolved orphans is aborted by End/watchdog/background/
   *  dispose. Terminal failures
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
      const ownMic = this.lastStatus?.micUnconfirmed === true;
      const ownIncomplete = this.cleanupIncomplete;
      if (ownMic || sharedGateState.micUnconfirmed) {
        if (sharedGateState.micUnconfirmed && !ownMic) this.surfaceSharedBlock();
        throw new Error(
          "Microphone release unconfirmed; End to retry before starting again."
        );
      }
      if (ownIncomplete || sharedGateState.cleanupIncomplete) {
        if (sharedGateState.cleanupIncomplete && !ownIncomplete && !ownMic) {
          this.surfaceSharedBlock();
        }
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
    if (this.orphans.size > 0 || sharedOrphans.size > 0 || sharedEndings.size > 0) {
      // An invalidated native Start is still unresolved, its late cleanup
      // unfinished, or a live release still in flight: do not open another
      // room behind it. Every orphan settles to disposal (generation
      // mismatch), never to an install — then this run proceeds. Report
      // pending now so the UI shows End instead of the stale pre-tap
      // status with no affordance; the wait itself aborts promptly when
      // this run is invalidated (End/watchdog/background/dispose), even
      // if the orphan never settles — still with nothing opened.
      const waiting: VoiceTestStatus = {
        state: "requesting",
        muted: false,
        participantCount: 0,
        errorMessage: "Waiting for previous session cleanup.",
      };
      this.lastStatus = waiting;
      this.onStatus(waiting);
      const proceeded = await this.waitForOrphans(generation);
      if (!proceeded) {
        // Invalidated while waiting: the caller below was already
        // released with the abort terminal, so just stop here with
        // nothing opened. The orphan's late settlement still reports
        // its own terminal through onStatus when it lands.
        this.clearWatchdogIfCurrent(generation);
        return null;
      }
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
        (this.lastStatus?.micUnconfirmed === true ||
          this.cleanupIncomplete ||
          sharedGateState.micUnconfirmed ||
          sharedGateState.cleanupIncomplete)
      ) {
        // An orphan settled while this tap waited — and its late cleanup
        // left release uncertain (with or without the mic flag): do not
        // open a room behind it. The orphan's handle was retained for End
        // retry; this tap ends here like a refused Start. When the block
        // comes from another screen, surface it here so the remounted UI
        // shows a usable End retry instead of stale waiting.
        const ownBlocking =
          this.lastStatus?.micUnconfirmed === true || this.cleanupIncomplete;
        if (!ownBlocking && (sharedGateState.micUnconfirmed || sharedGateState.cleanupIncomplete)) {
          this.surfaceSharedBlock();
        }
        this.clearWatchdogIfCurrent(generation);
        throw new Error(
          this.lastStatus?.micUnconfirmed === true || sharedGateState.micUnconfirmed
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
      // whether or not it carried the mic-unconfirmed flag. Mirrored
      // into the cross-session gate so a remounted screen fails closed too.
      try {
        await handle.end();
      } catch (error) {
        this.recoveryHandle = handle;
        this.cleanupIncomplete = true;
        sharedGateState.recovery = handle;
        sharedGateState.cleanupIncomplete = true;
        const message = error instanceof Error ? error.message : String(error);
        if (/unconfirmed/i.test(message) || this.lastStatus?.micUnconfirmed === true) {
          sharedGateState.micUnconfirmed = true;
        }
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
    // Release the caller promptly when this tap is invalidated
    // (End/watchdog/background/dispose) even if the stalled native
    // await never settles: the run itself continues in the background
    // so the orphan gate and late disposal are unchanged. A stalled
    // native await cannot be cancelled from JS — this only stops
    // WAITING for it. Registration is synchronous with the tap, so no
    // bump can slip between the run's first checks and this waiter.
    const abortedMarker: unique symbol = Symbol("voice-start-aborted");
    let onAbort: (() => void) | null = null;
    const aborted = new Promise<symbol>((resolve) => {
      onAbort = () => resolve(abortedMarker);
      if (this.disposed) {
        // Already torn down: never hang the caller.
        resolve(abortedMarker);
      } else {
        this.generationWaiters.add(onAbort);
      }
    });
    try {
      const outcome = await Promise.race([run, aborted]);
      if (typeof outcome === "symbol") {
        // Invalidated while pending: land the tap in a usable, truthful
        // state. This only ever replaces a stale pending display — a
        // terminal status the run already reported (denied/error/ended,
        // flags included) always stands. Nothing here implies a release
        // or opens a room. While a foreign shared release is still
        // pending, keep the Waiting display instead of inviting Start:
        // the release hasn't settled, so a startable-looking terminal
        // would be a false claim. (Own-orphan aborts keep the existing
        // retryable terminal.)
        const st = this.lastStatus;
        if (st !== null && (st.state === "requesting" || st.state === "connecting")) {
          const foreignSharedPending =
            sharedEndings.size > 0 || [...sharedOrphans].some((p) => !this.orphans.has(p));
          if (!foreignSharedPending) {
            const stopped: VoiceTestStatus = {
              state: "error",
              muted: false,
              participantCount: 0,
              errorMessage: "Start ended while pending; tap Start to retry.",
            };
            this.lastStatus = stopped;
            this.onStatus(stopped);
          }
        }
        return null;
      }
      return outcome;
    } finally {
      if (onAbort !== null) this.generationWaiters.delete(onAbort);
      if (this.starting === run) this.starting = null;
    }
  }
}
