/**
 * Foreground-only session orchestration for the LiveKit audio spike.
 *
 * Framework-free (no React, no native imports): the screen owns rendering
 * and passes platform dependencies in, so this module is unit-checkable
 * with plain Node and never pulls LiveKit into the web bundle.
 *
 * Guarantees:
 * - A Start that is still pending when the screen exits (or the app
 *   backgrounds) is disposed as soon as it completes — the room and
 *   audio session are never leaked behind a dead screen.
 * - The session handle is discarded only after cleanup settles; End
 *   works while Mute is pending, concurrent Ends share one teardown,
 *   and Mute/End failures stay visible instead of a false "ended".
 * - Genuine backgrounds end a live session (foreground-only test).
 *   Only the `background` state triggers this — never `inactive` — and
 *   only when a live handle exists, so the Android permission dialog
 *   during a pending Start can never falsely end the session.
 */
import type { VoiceTestHandle, VoiceTestStatus } from "./voice";

export interface VoiceTestSessionDeps {
  startVoiceTest: (
    onStatus: (status: VoiceTestStatus) => void
  ) => Promise<VoiceTestHandle>;
  getAppState: () => string;
  addAppStateListener: (onChange: (state: string) => void) => () => void;
}

export class VoiceTestSession {
  private handle: VoiceTestHandle | null = null;
  private generation = 0;
  private ending: Promise<void> | null = null;
  private disposed = false;
  private lastStatus: VoiceTestStatus | null = null;
  private removeAppStateListener: (() => void) | null = null;

  constructor(
    private readonly deps: VoiceTestSessionDeps,
    private readonly onStatus: (status: VoiceTestStatus) => void
  ) {
    this.removeAppStateListener = deps.addAppStateListener((state) =>
      this.onAppState(state)
    );
  }

  /** Start a session. Resolves to the live handle, or null when the start
   *  was overtaken (screen exit / background) and the late session was
   *  disposed. Terminal failures are reported through onStatus. */
  async start(): Promise<VoiceTestHandle | null> {
    const generation = this.generation;
    const previous = this.handle;
    this.handle = null;
    if (previous) {
      // End any previous session first so two rooms never run at once.
      // A failure here aborts the start: the old session may still be
      // live, and starting a second room would hide it.
      await previous.end();
    }
    if (
      this.disposed ||
      generation !== this.generation ||
      this.deps.getAppState() === "background"
    ) {
      // Overtaken while ending the previous session: do not open a room
      // behind a dead or backgrounded screen.
      return null;
    }
    let handle: VoiceTestHandle;
    try {
      handle = await this.deps.startVoiceTest((status) => {
        this.lastStatus = status;
        this.onStatus(status);
      });
    } catch (error) {
      if (this.disposed || generation !== this.generation) {
        // Overtaken while pending: native cleanup already ran; the
        // rejection only ends the orphaned start, so swallow it.
        return null;
      }
      throw error;
    }
    if (
      this.disposed ||
      generation !== this.generation ||
      this.deps.getAppState() === "background"
    ) {
      // Overtaken while pending: release the room/audio session as soon
      // as it completes. A disposal failure is already reported through
      // onStatus by the handle itself.
      await handle.end().catch(() => undefined);
      return null;
    }
    this.handle = handle;
    return handle;
  }

  async setMuted(muted: boolean): Promise<void> {
    const handle = this.handle;
    if (!handle) {
      throw new Error("No active session to mute.");
    }
    await handle.setMuted(muted);
  }

  /** End the session. Safe to call concurrently and repeatedly: one
   *  teardown runs, the handle is dropped only after it settles, and a
   *  teardown failure is reported through onStatus (error, not "ended"). */
  async end(): Promise<void> {
    const handle = this.handle;
    if (!handle) return;
    if (!this.ending) {
      this.ending = handle.end().finally(() => {
        if (this.handle === handle) this.handle = null;
        this.ending = null;
      });
    }
    return this.ending;
  }

  private onAppState(state: string): void {
    if (state !== "background") return;
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
    if (this.removeAppStateListener) {
      this.removeAppStateListener();
      this.removeAppStateListener = null;
    }
    void this.end().catch(() => undefined);
  }
}
