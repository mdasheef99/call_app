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
}

export interface VoiceTestHandle {
  setMuted(muted: boolean): Promise<void>;
  end(): Promise<void>;
}

export function getVoiceTestInitialStatus(): VoiceTestStatus {
  throw new Error("platform-specific module must implement getVoiceTestInitialStatus");
}

export function startVoiceTest(
  _onStatus: (status: VoiceTestStatus) => void
): Promise<VoiceTestHandle> {
  throw new Error("platform-specific module must implement startVoiceTest");
}
