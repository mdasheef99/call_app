/**
 * Web preview stub. There is intentionally NO browser voice integration
 * in this milestone — web is a shared-UI preview only, not a v1 product.
 */
export function getVoiceBackendStatus(): string {
  return "not supported on web preview (UI only)";
}

export function assertNoVoiceYet(): never {
  throw new Error("Voice is not available in the web preview.");
}

import type { VoiceTestHandle, VoiceTestStatus } from "./voice";

export function getVoiceTestInitialStatus(): VoiceTestStatus {
  return {
    state: "unsupported",
    muted: false,
    participantCount: 0,
    errorMessage: null,
  };
}

export function startVoiceTest(): Promise<VoiceTestHandle> {
  return Promise.reject(new Error("Voice test is not available in the web preview."));
}

/**
 * Truthful microphone label for display (mirrors `voice.ts` and
 * `voice.native.ts`; keep all three in sync). Web never publishes,
 * so this always reports off — the screen never shows a live
 * microphone in the preview.
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
