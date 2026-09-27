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
  *   stalls End — and the Start caller resolves promptly with a
  *   retryable error instead of hanging busy. A fresh Start waits for
  *   the orphan to settle instead of opening a second room behind it
  *   (safety over liveness), including orphans from a disposed screen
  *   (cross-session shared gate, P02: no duplicate active sessions).
 *   The wait itself is abortable: End, the watchdog, background, or
 *   disposal ends the tap promptly with nothing opened, even if the
 *   orphan never settles. While waiting, the tap reports pending so
 *   the UI shows End instead of a stale status with no affordance.
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
 *   or not, since a rejected end() is never proven release. Screen
 *   exit and backgrounding attempt that retained release too instead
 *   of dropping it with a possibly-live mic.
 * - Genuine backgrounds end a live session (foreground-only test).
 *   Only the `background` state triggers this — never `inactive`. A
 *   background with no live handle still attempts a retained uncertain
 *   release; the Android permission dialog during a pending Start
 *   (no handle, no uncertainty) can never falsely end the session.
 */
import type { VoiceTestStatus } from "./voice";
import {
  notifySharedSettled,
  sharedEndings,
  sharedGateState,
  sharedListeners,
  sharedMutes,
} from "./voice-shared-gate";
import { VOICE_TEST_WATCHDOG_MS } from "./voice-session-base";
import { VoiceSessionStarter } from "./voice-session-start";
import type { VoiceTestSessionDeps } from "./voice-session-base";

export { resetSharedVoiceGateForTests } from "./voice-shared-gate";
export { VOICE_TEST_WATCHDOG_MS };
export type { VoiceTestSessionDeps };

export class VoiceTestSession extends VoiceSessionStarter {
  async setMuted(muted: boolean): Promise<void> {
    const handle = this.handle;
    if (!handle) {
      throw new Error("No active session to mute.");
    }
    // Tracked so a remounted Start waits for an old in-flight mute to
    // settle instead of opening a room behind it; removed on settlement
    // (success or failure). End stays prompt — it never awaits this entry.
    // The no-op catch attach avoids an unhandled rejection if the toggle
    // later rejects after the caller was released by End/dispose.
    const gate: Promise<void> = handle.setMuted(muted);
    sharedMutes.add(gate);
    const done = () => {
      sharedMutes.delete(gate);
      notifySharedSettled();
    };
    void gate.then(done, done);
    try {
      await gate;
    } catch (error) {
      if (error instanceof Error && /unconfirmed/i.test(error.message)) {
        // Late mic failure (e.g. an Unmute compensation) with no local
        // retry left once disposed: hold the shared gate with this room as
        // the retry vehicle so a remount fails closed until End recovers it.
        sharedGateState.micUnconfirmed = true;
        sharedGateState.cleanupIncomplete = true;
        sharedGateState.recovery = handle;
        notifySharedSettled();
      }
      throw error;
    }
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
    // Falls back to the cross-session shared recovery so a remounted
    // screen can retry a disposed screen's failed release. A stale
    // recovery entry after a healthy End must stay untouched so repeat
    // Ends remain no-ops (single teardown). Never waits for a stalled
    // native Start: invalidation above detaches without waiting. Every
    // teardown registers in the shared endings gate so a remounted Start
    // waits for a held live release instead of opening a second room.
    const ownUncertain =
      this.lastStatus?.micUnconfirmed === true || this.cleanupIncomplete;
    const sharedUncertain = sharedGateState.micUnconfirmed || sharedGateState.cleanupIncomplete;
    const handle =
      this.handle ??
      (ownUncertain ? this.recoveryHandle : null) ??
      (sharedUncertain ? sharedGateState.recovery : null);
    if (!handle) return;
    const isSharedRecovery = handle === sharedGateState.recovery && this.handle !== handle;
    const isOwnHandle = this.handle === handle;
    if (!this.ending) {
      const teardown = handle.end().then(
        () => {
          // The live slot clears; the recovery slot deliberately lingers:
          // a mic-off failure can still land afterwards (late toggle
          // compensation), when no live handle exists to route End to.
          // A stale entry is a harmless no-op through the native shared
          // End promise, and Start gating reads the last status and the
          // incompleteness flag, never this slot. A resolved End proves
          // the release it attempted, so incompleteness clears here.
          // A matching shared recovery clears too so a remounted Start
          // unblocks; native terminals for own handles were already
          // reported through this session, but a shared retry must land
          // its own truthful terminal here (the native emit went dead).
          if (isOwnHandle) this.handle = null;
          this.cleanupIncomplete = false;
          if (sharedGateState.recovery === handle) {
            sharedGateState.cleanupIncomplete = false;
            sharedGateState.micUnconfirmed = false;
            sharedGateState.recovery = null;
          }
          if (isSharedRecovery) {
            const ended: VoiceTestStatus = {
              state: "ended",
              muted: false,
              participantCount: 0,
              errorMessage: null,
            };
            this.lastStatus = ended;
            this.onStatus(ended);
          }
          this.ending = null;
        },
        (error: unknown) => {
          // Any failed release stays retryable and fails closed across
          // remounts: retain the shared vehicle. Own terminals were
          // already reported through this session; a shared retry must
          // land its own truthful error here (the native emit went dead).
          const message = error instanceof Error ? error.message : String(error);
          const mic = /unconfirmed/i.test(message);
          sharedGateState.recovery = handle;
          sharedGateState.cleanupIncomplete = true;
          if (mic || this.lastStatus?.micUnconfirmed === true) {
            sharedGateState.micUnconfirmed = true;
          }
          if (isSharedRecovery) {
            const failed: VoiceTestStatus = {
              state: "error",
              muted: false,
              participantCount: 0,
              errorMessage: message,
              ...(sharedGateState.micUnconfirmed ? { micUnconfirmed: true } : {}),
              cleanupFailed: true,
            };
            this.lastStatus = failed;
            this.onStatus(failed);
          }
          this.ending = null;
          throw error;
        }
      );
      this.ending = teardown;
      sharedEndings.add(teardown);
      const removeEnding = () => {
        sharedEndings.delete(teardown);
        notifySharedSettled(this);
      };
      void teardown.then(removeEnding, removeEnding);
    }
    return this.ending;
  }

  protected onAppState(state: string): void {
    if (state !== "background") return;
    // Permanently invalidate any pending Start: even if the app returns
    // to the foreground before an await finishes, the orphaned run can
    // only dispose — a fresh tap is required to start again. Detached
    // without waiting (see invalidatePendingStart) so a stalled await
    // cannot stall this path either.
    this.clearWatchdog();
    this.invalidatePendingStart();
    // A retained uncertain release still needs its End retry even with
    // no live handle (e.g. a late mic-off failure after a healthy End),
    // including a disposed screen's shared recovery. Without uncertainty
    // there is nothing to release; without an active live session there
    // is nothing transmitting.
    const needsRecovery =
      this.lastStatus?.micUnconfirmed === true ||
      this.cleanupIncomplete ||
      sharedGateState.micUnconfirmed ||
      sharedGateState.cleanupIncomplete;
    if (!this.handle && !needsRecovery) return;
    if (this.handle && !needsRecovery) {
      const active =
        this.lastStatus === null ||
        this.lastStatus.state === "connected" ||
        this.lastStatus.state === "reconnecting";
      if (!active) return;
    }
    // Foreground-only test: stop transmission when genuinely backgrounded.
    // Fire-and-forget with errors already surfaced through onStatus.
    void this.end().catch(() => undefined);
  }

  /**
   * Screen exit: invalidate pending starts and release the session.
   * A retained uncertain release is attempted first: end() captures
   * the live/recovery handle synchronously, so clearing the recovery
   * slot afterwards keeps "cleared on dispose" while letting that
   * final attempt run instead of stranding a possibly-live mic.
   */
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.bumpGeneration();
    this.clearWatchdog();
    sharedListeners.delete(this.sharedEntry);
    if (this.removeAppStateListener) {
      this.removeAppStateListener();
      this.removeAppStateListener = null;
    }
    void this.end().catch(() => undefined);
    // Preserve the recovery vehicle across the screen boundary: a mic-off
    // failure can still land afterwards (late toggle compensation) when no
    // local retry remains. Transferred only into an empty slot so another
    // session's failed release is never clobbered; inert until shared flags
    // are set, so healthy disposes change nothing.
    if (this.recoveryHandle !== null && sharedGateState.recovery === null) {
      sharedGateState.recovery = this.recoveryHandle;
    }
    this.recoveryHandle = null;
    this.cleanupIncomplete = false;
  }
}
