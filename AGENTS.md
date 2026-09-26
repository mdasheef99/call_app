# AGENTS.md — working rules for this repo

## Current milestone: Android development-build setup

Foundation (PR #1) is merged. Current work prepares a local EAS Android
development-build configuration, including native LiveKit dependencies for
the later voice spike — no working voice. The Expo project is linked
(`@mdasheef/call-app-foundation`); WebRTC is pinned exact `144.1.2` and
cloud Node is pinned `22.23.2`. Two EAS Android attempts are recorded:
`5957da33` failed before the WebRTC correction; `9f539e50` finished with
an APK for corrected source `0c0751c` and is INSTALLED on the LG Wing
(dev-client launcher, Metro bundle, Home backend-ok, SIMULATED button
verified). A one-person mic/mute/End cycle was observed with OS-level
mic release. GitHub probe `35849621938` also assembled source `0c0751c`;
its packaged APK had RECORD_AUDIO and no CAMERA. EAS artifact manifest,
received audio, and any AI conversation remain UNTESTED, and every
future build needs the owner's explicit approval. Voice-draft
(local checkpoints, ahead of remote, not merged): prereq refusal before connect with `shutdown()` on
every refused job, explicit dispatch only (no single-job claim),
120 s active deadline (setup awaits+wait; sync model build not
preemptible; expiry decided by the timeout scope itself, so an SDK
`TimeoutError` is a setup failure only while `expired()` is false —
once the scope has expired it is reported as a deadline even if the
SDK converted the cancellation into a `TimeoutError`) then bounded
cleanup outside it (close/delete 10 s each
+ shutdown; no wall-clock or mic-release claim), phone-End via
session close even with room connected, session `CloseReason.ERROR`
as failure (content-free reason+type, never a successful end),
cancellation labeled cancelled with propagation, inner `TimeoutError`
preserved as setup failure, single deletion owner (SDK auto-delete
off, text input off), covered by offline tests (counts live only in
the latest dated HANDOFF checkpoint, not duplicated here)
— no server-side or device claim.
The call button stays SIMULATED UI state; native LiveKit code must never be
imported into shared/web code. No auth, database, memory, or analytics.

## Document precedence

1. `docs/Voice-Thinking-Partner-Prototype-Specification-v1.0.1.md` — locks v1 scope.
2. `docs/Architecture-Charter-Voice-Thinking-Partner-v0.2.md` — guarantees (auth, deletion, module boundaries).
3. `docs/Backend-Implementation-Blueprint-and-Architecture-Stress-Test-v0.2.md` — future design; do NOT implement beyond v1 scope.
4. `README.md` — setup/run and compatibility record. `docs/HANDOFF.md` — latest checkpoint status.

Do not edit the three specification files. Correct README/AGENTS/HANDOFF by editing, never by duplicating spec text.

## Verified commands (Windows PowerShell)

```powershell
# backend
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\backend\.venv\Scripts\python.exe -m pytest backend\tests -q
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# mobile (needs backend running for "Backend: ok")
cd mobile; npm install; npx tsc --noEmit; npx expo-doctor
npx expo start --web --port 8081   # manual check: http://localhost:8081/
npx expo export --platform web --output-dir dist-web
```

Results on record (foundation, merged PR #1 — historical): pytest 5 passed;
`tsc` exit 0; `expo-doctor` 18/18; web export 3 static routes; Playwright
browser inspection 0 console errors.
Voice-draft (local checkpoints, offline only — latest dated counts 2026-09-26):
backend pytest 42/42 (5 health + 37 voice-agent, per the 2026-09-26 HANDOFF
checkpoint; worker untouched since, not rerun); mobile `npm test` 78/78;
`tsc` 0; sanitized web export 4 routes (synthetic token-server marker and
agent name absent).
LiveKit (`livekit-agents==1.2.12` imports on Python 3.13) is a separate
experiment in `backend/.venv` only — NOT in requirements.

## Architectural boundaries

- Mobile talks to FastAPI; never to Supabase directly. No `service_role` key in the app.
- Native-only deps stay in `mobile/lib/*.native.ts`; web preview must bundle without them.
- Backend CORS allows local preview origins only (`localhost`/`127.0.0.1` ports 8081/19006), GET only, no wildcard.
- No Celery/Redis/Docker/WSL in this milestone; workers need Linux later.
- Supabase project for this work: `zyjylsvh…` (MCP `supabase_callapp`). The old project (`ahntbtkt…`, MCP `supabase_other`) stays disabled. Never run migrations without explicit approval, never push without approval.

## LiveKit free-plan testing gate

The `call_app` LiveKit Cloud project is on the free Build plan (read-only
dashboard check 2026-09-25; details in `docs/HANDOFF.md`). At the owner's
direction, pause all LiveKit experiments until the exact proposed run has
verified plan/remaining allowance, worker and dispatch behavior, any
external-provider cost, and a bounded stop/cleanup procedure. A 0% peak
concurrency reading is not proof of unused monthly allowance or zero cost.
For a mic-only trial, prove that the Start path cannot dispatch an agent;
an empty Agents page or omission of `agentName` alone is insufficient
(unnamed LiveKit workers auto-dispatch). This gate follows the owner's
instruction and Prototype Specification v1.0.1 sections 7.1 and 8.
If any part is uncertain, keep work offline. Each live connection still
needs the owner's separate explicit approval; no automatic retries, agent
deployments, or plan changes.

## Reporting requirements

Separate every report into: (1) browser UI opened/inspected, (2) automated
checks passed, (3) Android build completed, (4) physical-device tested.
Mark anything not performed as UNTESTED. Never claim a device or integration
works unless actually tested. Keep responses short; file paths as
`path:line`. No emojis in files.

## Process safety

- Never terminate processes by broad executable name (`python.exe`,
  `node.exe`, or similar). Stop only processes started for the current task,
  after verifying ownership using the recorded PID and available
  command/start-time information (e.g. `Get-Process -Id <pid>`).
- Preserve all unrelated applications and servers; leave other ports and
  work (e.g. Bookconnect on port 8082) untouched.
