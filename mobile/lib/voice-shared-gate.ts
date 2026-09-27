/**
 * Cross-screen shared gate for the LiveKit audio spike.
 *
 * Remounting the Audio Test screen disposes the old session, but its
 * stalled native await keeps running. A new session must wait for those
 * detached runs instead of opening a second room behind them (P02: no
 * duplicate active sessions). Module-shared singleton so every session
 * instance sees orphans from disposed screens; entries remove themselves
 * on settlement.
 *
 * Framework-free (no React, no native imports): never pulls LiveKit into
 * the web bundle. Synchronous registration/removal only; no awaits here.
 */
import type { VoiceTestHandle } from "./voice";

/** Listener entry for live remounted screens. Owner is compared by identity. */
export interface SharedGateListener {
  owner: object;
  notify: () => void;
}

export const sharedOrphans = new Set<Promise<VoiceTestHandle | null>>();

/**
 * Mutable cross-session release state. Held in one object (instead of
 * module lets) so every session module observes and updates the same
 * singleton through synchronous property access.
 */
export const sharedGateState: {
  cleanupIncomplete: boolean;
  micUnconfirmed: boolean;
  recovery: VoiceTestHandle | null;
} = {
  cleanupIncomplete: false,
  micUnconfirmed: false,
  recovery: null,
};

/**
 * In-flight live/recovery Ends shared across remounts. A new Start waits
 * for these to settle instead of opening a second room behind a held
 * release (P02). Entries remove themselves on settlement; a settled
 * failure leaves sharedGateState for fail-closed retry.
 */
export const sharedEndings = new Set<Promise<void>>();

/**
 * In-flight mute toggles shared across remounts. A remounted Start waits
 * for an old in-flight mute to settle instead of opening a room behind
 * it; entries remove themselves on settlement (success or failure), so
 * End stays prompt — it never awaits them. A late mic failure keeps its
 * shared fail-closed flags through the mute path below.
 */
export const sharedMutes = new Set<Promise<void>>();

/**
 * Live remounted screens subscribed for shared release outcomes. A new
 * screen that never taps Start still needs the outcome: pending while a
 * release is held, actionable error on failure, startable idle on
 * success. Entries are added on construction and removed on disposal, so
 * a disposed screen never receives late updates. Notifications never
 * start rooms or retry releases by themselves.
 */
export const sharedListeners = new Set<SharedGateListener>();

/** Notify live subscribers of a settled shared release, except its owner:
 * the owner already landed its own terminal (ended/error) through its own
 * path, so only the remounted screens need the outcome surfaced. */
export function notifySharedSettled(except?: object): void {
  for (const entry of [...sharedListeners]) {
    if (except !== undefined && entry.owner === except) continue;
    entry.notify();
  }
}

/** Test-only reset for deterministic isolation (each test starts clean). */
export function resetSharedVoiceGateForTests(): void {
  sharedOrphans.clear();
  sharedGateState.cleanupIncomplete = false;
  sharedGateState.micUnconfirmed = false;
  sharedGateState.recovery = null;
  sharedEndings.clear();
  sharedMutes.clear();
  sharedListeners.clear();
}
