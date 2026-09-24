/**
 * Native-only LiveKit audio test (Android development build target).
 * All LiveKit/webrtc imports live in this file so web bundling
 * (which resolves `voice.web.ts` instead) never sees them.
 *
 * Audio-only experiment: microphone publish + remote-audio playback.
 * No camera, video, recording, transcript, or AI-agent behavior.
 *
 * Credentials are minted on demand per Start via LiveKit Cloud's
 * development token server (already-installed `livekit-client`
 * `TokenSource`; no static token is embedded in the app). Dev-only,
 * never for pilot/production.
 */
import { AudioSession, AndroidAudioTypePresets, registerGlobals } from "@livekit/react-native";
import { Room, RoomEvent, TokenSource } from "livekit-client";
import { getVoiceTestConfig } from "./voice-config";
import type {
  VoiceTestHandle,
  VoiceTestState,
  VoiceTestStatus,
} from "./voice";

registerGlobals();

export function getVoiceBackendStatus(): string {
  return "not implemented — requires Expo development build (not Expo Go)";
}

export function assertNoVoiceYet(): never {
  throw new Error(
    "Voice is not implemented in the foundation milestone. Requires an Expo development build."
  );
}

function baseStatus(state: VoiceTestState): VoiceTestStatus {
  return { state, muted: false, participantCount: 0, errorMessage: null };
}

/**
 * Truthful microphone label for display. Live is reported only after
 * publishing succeeds (`connected`/`reconnecting`, honoring the mute
 * toggle). Every other state — idle, needs-config, requesting,
 * connecting, denied, error, ended — reports off, even though the
 * shared `muted` flag defaults to false. (Base contract in `voice.ts`
 * and web mirror in `voice.web.ts`; keep all three in sync.)
 */
export function describeMicrophone(status: VoiceTestStatus): string {
  if (status.state === "connected" || status.state === "reconnecting") {
    return status.muted ? "muted" : "live";
  }
  return "off";
}

export function getVoiceTestInitialStatus(): VoiceTestStatus {
  const config = getVoiceTestConfig();
  if (!config.ok) return baseStatus("needs-config");
  return baseStatus("idle");
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isPermissionDenial(error: unknown): boolean {
  const text = `${error instanceof Error ? `${error.name} ${error.message}` : String(error)}`;
  return /permission|notallowed|not allowed|denied/i.test(text);
}

export async function startVoiceTest(
  onStatus: (status: VoiceTestStatus) => void
): Promise<VoiceTestHandle> {
  const config = getVoiceTestConfig();
  if (!config.ok) {
    throw new Error(
      `Voice test is not configured. Set ${config.missing.join(" and ")} in mobile/.env (never commit the value).`
    );
  }

  const room = new Room();
  let settled = false;
  let muted = false;
  // True only after setMicrophoneEnabled(true) succeeds: `connected` /
  // `reconnecting` states (which the microphone display maps to
  // live/muted) may not be entered before the microphone is published.
  let published = false;
  let endPromise: Promise<void> | null = null;
  // participantCount 0 until Connected: no room exists during token mint
  // and audio setup, so a count of 1 would not be truthful.
  let status: VoiceTestStatus = baseStatus("requesting");

  const emit = (next: VoiceTestStatus) => {
    status = next;
    onStatus(next);
  };
  const count = () => room.remoteParticipants.size + 1;

  const fail = async (state: Extract<VoiceTestState, "denied" | "error">, error: unknown) => {
    if (settled) return;
    settled = true;
    const message = messageOf(error);
    try {
      await room.disconnect(true);
    } catch {
      // Best effort: the room is unusable; report the original failure.
    }
    try {
      await AudioSession.stopAudioSession();
    } catch {
      // Best effort: release whatever was started.
    }
    emit({ ...baseStatus(state), participantCount: 0, errorMessage: message });
    throw error instanceof Error ? error : new Error(message);
  };

  // Unexpected remote/network disconnect: full terminal cleanup
  // (microphone off, disconnect best-effort, audio session stopped,
  // listeners removed) reporting error — never a false "ended".
  // Mutual exclusion via `settled` keeps this safe against a concurrent
  // End, screen exit, or start-failure path: exactly one path owns the
  // terminal state, and the shared `endPromise` below stays resolved
  // without overwriting it.
  let unexpectedDisconnect: Promise<void> | null = null;
  const cleanupOnUnexpectedDisconnect = () => {
    if (!unexpectedDisconnect) {
      unexpectedDisconnect = (async () => {
        settled = true;
        try {
          await room.localParticipant.setMicrophoneEnabled(false);
        } catch {
          // Best effort: the track may already be gone.
        }
        try {
          await room.disconnect(true);
        } catch {
          // Best effort: the transport is already down.
        }
        try {
          await AudioSession.stopAudioSession();
        } catch {
          // Best effort: release whatever was started.
        } finally {
          room.removeAllListeners();
        }
        emit({
          ...baseStatus("error"),
          muted,
          participantCount: 0,
          errorMessage: "Disconnected unexpectedly.",
        });
      })();
    }
    return unexpectedDisconnect;
  };

  room
    .on(RoomEvent.Connected, () => {
      if (settled) return;
      if (!published) {
        // Initial connection completes before the microphone publishes;
        // stay in `connecting` so the display never claims a live mic
        // until publish succeeds. The count is truthful: we are already
        // in the room even though audio is not yet flowing.
        emit({ ...status, state: "connecting", participantCount: count() });
        return;
      }
      emit({ ...baseStatus("connected"), muted, participantCount: count() });
    })
    .on(RoomEvent.Reconnecting, () => {
      if (settled) return;
      emit({ ...status, state: published ? "reconnecting" : "connecting", participantCount: count() });
    })
    .on(RoomEvent.Reconnected, () => {
      if (settled) return;
      emit({ ...status, state: published ? "connected" : "connecting", participantCount: count() });
    })
    .on(RoomEvent.ParticipantConnected, () => {
      if (!settled && status.state === "connected") {
        emit({ ...status, participantCount: count() });
      }
    })
    .on(RoomEvent.ParticipantDisconnected, () => {
      if (!settled && status.state === "connected") {
        emit({ ...status, participantCount: count() });
      }
    })
    .on(RoomEvent.Disconnected, () => {
      // Our own teardown already set `settled` and emitted its terminal
      // state, so only an unexpected disconnect reaches cleanup here.
      if (settled) return;
      void cleanupOnUnexpectedDisconnect();
    });

  try {
    emit({ ...status, state: "requesting" });
    // Mint a short-lived development token on demand. No room name is
    // requested, so the server issues a fresh room per Start — concurrent
    // starts never share a room.
    const tokenSource = TokenSource.developmentTokenServer(
      config.config.tokenServerId
    );
    const connection = await tokenSource.fetch({
      participantName: "voice-spike",
    });
    if (!connection.serverUrl || !connection.participantToken) {
      throw new Error("Development token server returned incomplete credentials.");
    }
    emit({ ...status, state: "connecting" });
    // Voice-call routing preset (documented AndroidAudioTypePresets).
    await AudioSession.configureAudio({
      android: { audioTypeOptions: AndroidAudioTypePresets.communication },
    });
    await AudioSession.startAudioSession();
    await room.connect(connection.serverUrl, connection.participantToken);
    if (settled) {
      // An unexpected disconnect landed mid-start; its cleanup owns the
      // terminal state, so reject Start instead of reporting connected.
      throw new Error("Disconnected unexpectedly.");
    }
    // Publishes the microphone; the OS permission prompt appears here
    // on first use because this only ever runs after the user taps Start.
    await room.localParticipant.setMicrophoneEnabled(true);
    if (settled) {
      // The session ended while publishing; teardown owns the terminal
      // state, so reject Start instead of reporting a stale connected.
      throw new Error("Disconnected unexpectedly.");
    }
    muted = false;
    published = true;
    emit({ ...baseStatus("connected"), participantCount: count() });
  } catch (error) {
    await fail(isPermissionDenial(error) ? "denied" : "error", error);
    // `fail` rethrows when it owns the terminal state; when another path
    // (unexpected disconnect) already settled, reject Start explicitly so
    // a connection-time failure never resolves with a handle.
    throw error instanceof Error ? error : new Error(messageOf(error));
  }

  async function teardown(): Promise<void> {
    // Idempotent: an unexpectedly-disconnected session has nothing left
    // to release (its cleanup already disconnected and stopped the
    // session and owns the terminal state). End still waits for that
    // in-flight cleanup so resources settle exactly once and the error
    // status is final before End resolves.
    if (settled) {
      if (unexpectedDisconnect) await unexpectedDisconnect.catch(() => undefined);
      return;
    }
    settled = true;
    try {
      await room.localParticipant.setMicrophoneEnabled(false);
    } catch {
      // Best effort: the track may already be gone.
    }
    try {
      await room.disconnect(true);
    } finally {
      try {
        await AudioSession.stopAudioSession();
      } finally {
        room.removeAllListeners();
      }
    }
    emit({ ...baseStatus("ended"), muted });
  }

  return {
    async setMuted(next: boolean): Promise<void> {
      if (settled) {
        throw new Error("Session has ended; mute is not available.");
      }
      try {
        await room.localParticipant.setMicrophoneEnabled(!next);
      } catch (error) {
        // Stay in the current state but surface the failure: the
        // microphone may still be live, so never report success. When the
        // session ended concurrently, its own terminal state stands.
        const message = messageOf(error);
        if (!settled) emit({ ...status, errorMessage: message });
        throw error instanceof Error ? error : new Error(message);
      }
      if (settled) {
        // End won the race while the toggle was in flight; teardown owns
        // the terminal state, so report honestly instead of stale success.
        throw new Error("Session ended while changing mute.");
      }
      muted = next;
      emit({ ...status, muted, errorMessage: null });
    },
    async end(): Promise<void> {
      // Shared promise: concurrent and repeated calls (End button,
      // screen exit, backgrounding) run teardown exactly once.
      if (!endPromise) {
        endPromise = teardown().catch((error: unknown) => {
          // Report teardown failure honestly: the microphone may still
          // be live, so show error — never a false "ended".
          const message = messageOf(error);
          emit({ ...baseStatus("error"), muted, errorMessage: message });
          throw error instanceof Error ? error : new Error(message);
        });
      }
      return endPromise;
    },
  };
}
