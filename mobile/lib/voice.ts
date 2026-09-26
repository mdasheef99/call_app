/**
 * Shared voice-status contract.
 * Native audio (LiveKit) is NOT wired in this milestone.
 * Real implementation will live behind `voice.native.ts` so web bundling
 * never pulls in native-only modules (react-native-webrtc).
 */
export function getVoiceBackendStatus(): string {
  throw new Error("platform-specific module must implement getVoiceBackendStatus");
}

export function assertNoVoiceYet(): never {
  throw new Error(
    "Voice is not implemented in the foundation milestone. Requires an Expo development build."
  );
}

/**
 * Development audio-test contract (LiveKit spike).
 * States mirror the v1 call lifecycle in miniature: connecting,
 * connected/active, reconnecting, ended/failed, plus explicit
 * `needs-config`, `denied`, and `unsupported` (web) states.
 * Real behavior lives behind `voice.native.ts`; web stays a stub.
 */
export type VoiceTestState =
  | "unsupported"
  | "needs-config"
  | "idle"
  | "requesting"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "denied"
  | "error"
  | "ended";

export interface VoiceTestStatus {
  state: VoiceTestState;
  muted: boolean;
  participantCount: number;
  errorMessage: string | null;
  /**
   * Set only when a mic-off attempt threw: the microphone may still be
   * live, so its release is unconfirmed — never display it as off.
   * Absent/false everywhere else.
   */
  micUnconfirmed?: boolean;
  /**
   * Set on error statuses from a failed End/teardown while the handle is
   * retained for retry: the screen offers End again and withholds Start.
   * Independent of micUnconfirmed — a disconnect failure leaves the mic
   * confirmed off (label stays "off") while cleanup still needs a retry.
   * Absent/false everywhere else.
   */
  cleanupFailed?: boolean;
}

export interface VoiceTestHandle {
  setMuted(muted: boolean): Promise<void>;
  end(): Promise<void>;
}

/**
 * Truthful microphone label for display. Live is reported only after
 * publishing succeeds (`connected`/`reconnecting`, honoring the mute
 * toggle). Every other state — idle, needs-config, requesting,
 * connecting, denied, error, ended, unsupported — reports off, even
 * though the shared `muted` flag defaults to false. (Native and web
 * mirror this in `voice.native.ts`/`voice.web.ts` for Metro runtime
 * resolution; keep all three in sync.)
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
  throw new Error("platform-specific module must implement getVoiceTestInitialStatus");
}

export function startVoiceTest(
  _onStatus: (status: VoiceTestStatus) => void,
  _shouldAbort?: () => boolean
): Promise<VoiceTestHandle> {
  throw new Error("platform-specific module must implement startVoiceTest");
}
