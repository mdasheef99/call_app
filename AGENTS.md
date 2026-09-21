# AGENTS.md — working rules for this repo

## Current milestone: foundation only

Minimal Expo web-preview shell + FastAPI health endpoints. No auth, database,
voice, memory, analytics, or new UI features. The call button is SIMULATED
UI state and must stay labelled as such; never report it as functioning voice.

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
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\.venv\Scripts\python.exe -m pytest backend\tests -q
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# mobile (needs backend running for "Backend: ok")
cd mobile; npm install; npx tsc --noEmit; npx expo-doctor
npx expo start --web --port 8081   # manual check: http://localhost:8081/
npx expo export --platform web --output-dir dist-web
```

Results on record: pytest 3 passed; `tsc` exit 0; `expo-doctor` 18/18;
web export 3 static routes; Playwright browser inspection 0 console errors.
LiveKit (`livekit-agents==1.2.12` imports on Python 3.13) is a separate
experiment in `backend/.venv` only — NOT in requirements.

## Architectural boundaries

- Mobile talks to FastAPI; never to Supabase directly. No `service_role` key in the app.
- Native-only deps stay in `mobile/lib/*.native.ts`; web preview must bundle without them.
- Backend CORS allows local preview origins only (`localhost`/`127.0.0.1` ports 8081/19006), GET only, no wildcard.
- No Celery/Redis/Docker/WSL in this milestone; workers need Linux later.
- Supabase project for this work: `zyjylsvh…` (MCP `supabase_callapp`). The old project (`ahntbtkt…`, MCP `supabase_other`) stays disabled. Never run migrations without explicit approval, never push without approval.

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
