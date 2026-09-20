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
