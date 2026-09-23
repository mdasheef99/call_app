/**
 * Development-only LiveKit credentials for the native audio spike.
 *
 * Pure shared module: no native imports, safe to unit-check with plain
 * Node. The value comes from `mobile/.env` (gitignored, never committed)
 * and is inlined by Metro at bundle time.
 *
 * There is intentionally NO static participant token in this spike.
 * Tokens are minted on demand at Start time through LiveKit Cloud's
 * development token server (`TokenSource.developmentTokenServer` in the
 * already-installed `livekit-client` package): short-lived (~15 min),
 * scoped to one fresh room per Start, never embedded in client
 * JavaScript, never committed.
 *
 * The token-server ID is development-only and MUST stay unset by
 * default: anyone holding it can mint development tokens for the
 * project without further authentication. Never use this mechanism for
 * pilot or production traffic — that needs a backend token endpoint
 * with account authorization (separate future work).
 */
export const VOICE_TEST_TOKEN_SERVER_ID_ENV =
  "EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID";

export interface VoiceTestConfig {
  tokenServerId: string;
}

export type VoiceTestConfigResult =
  | { ok: true; config: VoiceTestConfig }
  | { ok: false; missing: string[] };

export function getVoiceTestConfig(): VoiceTestConfigResult {
  const tokenServerId = (
    process.env[VOICE_TEST_TOKEN_SERVER_ID_ENV] ?? ""
  ).trim();
  if (!tokenServerId) {
    return { ok: false, missing: [VOICE_TEST_TOKEN_SERVER_ID_ENV] };
  }
  return { ok: true, config: { tokenServerId } };
}
