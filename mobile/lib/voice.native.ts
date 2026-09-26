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
import { VOICE_AGENT_NAME } from "./voice-config";
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
  // A failed mic-off leaves the microphone possibly live: report the
  // release as unconfirmed rather than a false "off" (or a stale live).
  if (status.micUnconfirmed) return "unconfirmed";
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

/** Terminal message when a mic-off attempt threw: the mic may still be live. */
function unconfirmedMessage(error: unknown): string {
  return `Microphone release unconfirmed: ${messageOf(error)}`;
}

function isPermissionDenial(error: unknown): boolean {
  const text = `${error instanceof Error ? `${error.name} ${error.message}` : String(error)}`;
  return /permission|notallowed|not allowed|denied/i.test(text);
}

export async function startVoiceTest(
  onStatus: (status: VoiceTestStatus) => void,
  _shouldAbort?: () => boolean
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
  // Set whenever a mic-off attempt throws, in any path: the microphone
  // may still be live, so terminal statuses must show the release as
  // unconfirmed instead of a false "off"/"ended".
  let releaseUnconfirmed = false;
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
      await room.localParticipant.setMicrophoneEnabled(false);
    } catch {
      // Best effort here, but never silent: the mic may still be live,
      // so the terminal status shows the release as unconfirmed.
      // Still disconnect/stop below; the original failure is reported
      // (never ended).
      releaseUnconfirmed = true;
    }
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
    emit({
      ...baseStatus(state),
      participantCount: 0,
      errorMessage: releaseUnconfirmed ? `${message} (microphone release unconfirmed)` : message,
      ...(releaseUnconfirmed ? { micUnconfirmed: true } : {}),
    });
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
  let unexpectedMicError: unknown = null;
  const emitUnexpectedStatus = () => {
    emit({
      ...baseStatus("error"),
      muted,
      participantCount: 0,
      errorMessage: unexpectedMicError
        ? `Disconnected unexpectedly. ${unconfirmedMessage(unexpectedMicError)}`
        : "Disconnected unexpectedly.",
      ...(unexpectedMicError ? { micUnconfirmed: true } : {}),
    });
  };
  const cleanupOnUnexpectedDisconnect = () => {
    if (!unexpectedDisconnect) {
      unexpectedDisconnect = (async () => {
        settled = true;
        try {
          await room.localParticipant.setMicrophoneEnabled(false);
        } catch (error) {
          // Track release failure so End rejects instead of resolving
          // while the mic state is unconfirmed; the status below shows
          // the release as unconfirmed rather than a false "off".
          unexpectedMicError = error;
          releaseUnconfirmed = true;
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
        emitUnexpectedStatus();
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

  const runTeardown = (recover = false) =>
    teardown(recover).catch((error: unknown) => {
      // Report teardown failure honestly: when a mic-off attempt
      // threw, the microphone may still be live, so show the
      // release as unconfirmed — never a false "ended" or "off".
      // The rejection carries the same wording (original kept as
      // cause) so log readers see the uncertainty too.
      const message = messageOf(error);
      const unconfirmed = releaseUnconfirmed || unexpectedMicError != null;
      const report = unconfirmed
        ? `Microphone release unconfirmed: ${message}`
        : message;
      emit({
        ...baseStatus("error"),
        muted,
        errorMessage: report,
        ...(unconfirmed ? { micUnconfirmed: true } : {}),
        // The handle is retained for retry in both branches below, so the
        // screen offers End again and withholds Start — whether or not the
        // mic flag was set. A disconnect failure leaves micUnconfirmed
        // absent (mic-off succeeded; label stays "off").
        cleanupFailed: true,
      });
      if (!unexpectedDisconnect) {
        settled = false;
        endPromise = null;
      }
      if (unconfirmed) {
        throw new Error(report, {
          cause: error instanceof Error ? error : new Error(message),
        });
      }
      throw error instanceof Error ? error : new Error(message);
    });

  /**
   * Session handle. Resolved live on a successful Start; also resolved
   * as a recovery-only vehicle when the Start itself failed with an
   * unconfirmed mic release (the session stashes it for End retry
   * instead of treating it as live — see the catch below).
   * setMuted on a settled session always rejects; End always routes to
   * teardown, which retries mic-off fresh whenever uncertainty remains.
   */
  const handle: VoiceTestHandle = {
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
        // End won the race while the toggle was in flight: force the mic
        // back off so a late enable cannot survive "ended", then report
        // honestly instead of stale success. If the compensation fails
        // the mic may be live behind "ended": supersede it with a
        // release-unconfirmed error (never a silent stale terminal).
        let compensatingError: unknown = null;
        try {
          await room.localParticipant.setMicrophoneEnabled(false);
        } catch (error) {
          compensatingError = error;
        }
        if (compensatingError) {
          releaseUnconfirmed = true;
          const message = unconfirmedMessage(compensatingError);
          emit({
            ...baseStatus("error"),
            muted,
            participantCount: 0,
            errorMessage: message,
            micUnconfirmed: true,
          });
          throw new Error(message);
        }
        throw new Error("Session ended while changing mute.");
      }
      muted = next;
      emit({ ...status, muted, errorMessage: null });
    },
    async end(): Promise<void> {
      // Shared promise: concurrent calls run teardown exactly once —
      // unless mic state is uncertain, in which case the next End makes
      // a fresh mic-off attempt: directly for a first End on a recovery
      // handle, or queued behind the settled promise afterwards
      // (teardowns never run concurrently). Capturing the flag keeps
      // concurrent Ends sharing that single queued attempt; a failed
      // attempt re-arms it. A rejected cleanup without uncertainty
      // clears ownership so a later End retries.
      if (!endPromise) {
        endPromise = runTeardown(releaseUnconfirmed);
      } else if (releaseUnconfirmed) {
        releaseUnconfirmed = false;
        const prior = endPromise;
        endPromise = prior.then(
          () => runTeardown(true),
          () => runTeardown(true)
        );
      }
      return endPromise;
    },
  };

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
      // Explicit named dispatch: the token server embeds a dispatch for
      // VOICE_AGENT_NAME in this fresh room. Sent only here (post-tap),
      // so no agent starts, joins, or is duplicated otherwise.
      agentName: VOICE_AGENT_NAME,
    });
    if (!connection.serverUrl || !connection.participantToken) {
      throw new Error("Development token server returned incomplete credentials.");
    }
    if (_shouldAbort?.()) {
      // Invalidated while the token fetch was in flight (End, watchdog,
      // background, disposal): reject before opening a room, starting
      // audio, or publishing — a late token result must never open a room.
      throw new Error("Start overtaken; session disposed.");
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
    if (_shouldAbort?.()) {
      // Disposed/backgrounded while pending; reject before publishing.
      throw new Error("Start overtaken; session disposed.");
    }
    // Publishes the microphone; the OS permission prompt appears here
    // on first use because this only ever runs after the user taps Start.
    await room.localParticipant.setMicrophoneEnabled(true);
    if (settled || _shouldAbort?.()) {
      // The session ended while publishing: the mic may now be live
      // behind a settled session, so force it back off before rejecting
      // — a late publish must never survive End. If the compensation
      // itself fails the release is unconfirmed (never a silent
      // "ended"); teardown already owns the terminal state otherwise,
      // so reject Start instead of reporting a stale connected.
      let compensatingError: unknown = null;
      try {
        await room.localParticipant.setMicrophoneEnabled(false);
      } catch (error) {
        compensatingError = error;
      }
      if (compensatingError) {
        releaseUnconfirmed = true;
        emit({
          ...baseStatus("error"),
          muted,
          participantCount: 0,
          errorMessage: unconfirmedMessage(compensatingError),
          micUnconfirmed: true,
        });
      }
      throw new Error("Disconnected unexpectedly.");
    }
    muted = false;
    published = true;
    emit({ ...baseStatus("connected"), participantCount: count() });
  } catch (error) {
    // `fail` rethrows when it owns the terminal state; when another path
    // (unexpected disconnect) already settled, it resolves quietly. Either
    // way a connection-time failure never resolves with a LIVE handle —
    // but when the release is unconfirmed (a mic-off attempt threw and
    // the mic may still be live), resolve with this room as a
    // recovery-only vehicle instead of throwing it away: the session
    // stashes it for the displayed End, whose teardown retries mic-off
    // fresh. Without uncertainty, reject as before.
    await fail(isPermissionDenial(error) ? "denied" : "error", error).catch(
      () => undefined
    );
    if (releaseUnconfirmed) return handle;
    throw error instanceof Error ? error : new Error(messageOf(error));
  }

  async function teardown(recover = false): Promise<void> {
    // Idempotent: an unexpectedly-disconnected session has nothing left
    // to release (its cleanup already disconnected and stopped the
    // session and owns the terminal state). End still waits for that
    // in-flight cleanup so resources settle exactly once and the error
    // status is final before End resolves — except that uncertain mic
    // state is retried fresh below (recovery), never rethrown stale and
    // never silently skipped.
    if (settled) {
      if (unexpectedDisconnect) {
        await unexpectedDisconnect.catch(() => undefined);
        if (unexpectedMicError || releaseUnconfirmed) {
          // Recovery: the displayed End retries mic-off fresh — whether
          // the cleanup's own mic-off failed or a later compensation
          // did. Success clears the uncertainty (the plain disconnect
          // error stands); failure keeps the warning and stays retryable.
          try {
            await room.localParticipant.setMicrophoneEnabled(false);
          } catch (error) {
            // State updated; the End wrapper below emits the unconfirmed
            // status and keeps this retryable.
            unexpectedMicError = error;
            releaseUnconfirmed = true;
            throw unexpectedMicError;
          }
          unexpectedMicError = null;
          releaseUnconfirmed = false;
          emitUnexpectedStatus();
        }
        return;
      }
      // Settled by a successful teardown, but a late mic-off failure
      // landed afterwards: only a recovery End (recover=true) runs a
      // fresh full attempt here — ordinary repeat Ends stay exactly-once
      // no-ops below, preserving the single-teardown guarantee.
      if (!recover) return;
    }
    settled = true;
    // Fresh attempt: an earlier failed End may have set this; only this
    // attempt's mic-off outcome decides the next terminal status.
    releaseUnconfirmed = false;
    let micError: unknown = null;
    try {
      await room.localParticipant.setMicrophoneEnabled(false);
    } catch (error) {
      // Never swallow: mic may still be live, so teardown must fail
      // rather than emit a false "ended". Still run disconnect/stop below.
      // The End rejection below carries the release-unconfirmed status.
      micError = error;
      releaseUnconfirmed = true;
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
    if (micError) throw micError;
    emit({ ...baseStatus("ended"), muted });
  }

  return handle;
}
