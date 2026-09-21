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
