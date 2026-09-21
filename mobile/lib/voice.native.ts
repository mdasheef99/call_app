/**
 * Native-only voice entry point (Android development build target).
 * Deliberately has NO imports of webrtc/LiveKit yet — adding them here keeps
 * them out of the web bundle via platform-specific resolution (*.native.ts).
 */
export function getVoiceBackendStatus(): string {
  return "not implemented — requires Expo development build (not Expo Go)";
}

export function assertNoVoiceYet(): never {
  throw new Error(
    "Voice is not implemented in the foundation milestone. Requires an Expo development build."
  );
}
