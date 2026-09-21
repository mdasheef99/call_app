# HANDOFF — foundation correction checkpoint

Date: 2026-09-21. Base code revision: `master` `9167a74` (origin/main
`c8930e1`, README only; histories unrelated). This correction round is
uncommitted on top of `9167a74`; code changes are limited to 2 new CORS
regression tests and lockfile BOM removal, plus doc/env-template fixes.
No merge, no push yet.

## Completed work (this round, on top of the foundation)

- `AGENTS.md`: durable process-safety rule (never kill by broad exe name;
  stop only own PIDs after ownership check; preserve unrelated servers).
- `backend/tests/test_health.py`: kept the allowed-origin test; added
  unlisted-origin (no ACAO header) and POST-preflight-rejected (400,
  GET-only) tests. CORS documented as preview policy, not authentication.
- `backend/requirements.lock`: removed UTF-8 BOM (entries unchanged, LF).
- `.env.example`: removed unconsumed `BACKEND_HOST`/`BACKEND_PORT`;
  documents `mobile/.env` location and explicit uvicorn CLI flags.
- `README.md`: phone command now invokes `.\backend\.venv\Scripts\python.exe
  -m uvicorn` from the repo root; local (`127.0.0.1`) vs LAN (`0.0.0.0`)
  kept separate; verification section reconciled (see below).

## Completed work (foundation, prior round)

- Minimal Expo SDK 54.0.37 / RN 0.81.5 / React 19.1.0 / expo-router 6.0.24 app
  with one Home screen; web preview supported; native-only code isolated in
  `mobile/lib/*.native.ts`; call button labelled SIMULATED throughout.
- Minimal FastAPI app (`GET /health`, `GET /v1/status`) with local-preview
  CORS (GET only, no wildcard); 3 pytest tests.
- Fixes this round: aligned `babel-preset-expo` (~54.0.10, was wrongly 14.0.6)
  and `react-native` (0.81.5) via `npx expo install --fix`; added backend CORS
  after browser inspection proved the web preview couldn't reach the API;
  corrected README on bundled-JDK Gradle use; kept Expo-generated
  `tsconfig.json`/`mobile/.gitignore` additions.
- LiveKit `1.2.12` import verified on Python 3.13 in `backend/.venv` only;
  not in committed requirements.

## Verification evidence

Checks rerun in this correction round (working tree on top of `9167a74`):

- `pytest backend/tests -q`: 5 passed (3 existing + 2 new CORS tests).
- `npx tsc --noEmit`: exit 0. `npx expo-doctor`: 18/18.
- `npx expo export --platform web` to disposable Temp output: 3 static
  routes (`/`, `/_sitemap`, `/+not-found`); repo tree unpolluted.
- Phone-style startup verified with the documented venv command on unused
  port 18080 (`GET /health` returned `{"status":"ok",...}`); only the
  started PID was stopped.

Earlier implementation evidence (2026-09-20, not rerun here):

- `pytest` 3 passed in a fresh venv from committed instructions; freeze
  identical; temp env removed.
- `npx expo export --platform web`: 3 static routes.
- Playwright browser inspection of `http://localhost:8081/` (backend live):
  Home renders, `Backend: ok (0.0.1-foundation)`, button toggles to
  `End simulated call` / `SIMULATED CALL ACTIVE (UI state only)`,
  0 console errors (1 framework `pointerEvents` deprecation warning).

Independent reviewers' checks at `9167a74` (review-only runs, not a
substitute for the checks above): pytest 3 passed, `tsc` exit 0,
`expo-doctor` 18/18, live health-check ok.

## Untested

- Android build: UNTESTED (no Studio/SDK/adb on this machine).
- Physical device: UNTESTED (no device, no voice implemented).
- Interactive check command for the owner: run backend + `cd mobile`,
  `npx expo start --web --port 8081`, open `http://localhost:8081/`.

## Blockers / notes

- Dev servers stopped after inspection; ports 8000/8081 free. Other running
  servers (port 8082, Bookconnect) belong to other work — untouched.
- One broad `Stop-Process` on `python.exe` was used mid-task; future kills
  must target PIDs/command lines only.
- Supabase: new project `zyjylsvh…` clean (0 tables); old `ahntbtkt…`
  disabled in opencode config. No migrations run or planned this milestone.
- OpenCode version on record: 1.14.33. No global permission changes made.

## Next action — publication procedure (document only, do not execute here)

1. Fetch and inspect `origin/main` (`git fetch origin`, `git log origin/main`,
   `git ls-tree origin/main`); confirm whether histories are still unrelated.
2. Preserve the local implementation branch (`master` at its committed SHA);
   do not reset, amend, or rewrite it.
3. Create `review/foundation` from `origin/main`.
4. Merge the implementation branch into it, using
   `--allow-unrelated-histories` if the histories are still unrelated.
5. Resolve `README.md` by inspecting both contents (ours/theirs labels are
   ambiguous for a full rewrite); keep the foundation README deliberately.
6. Review the resulting diff and rerun the checks before any push.
7. Push only the `review/foundation` branch and open a draft PR when the
   owner authorizes it. Never force-push `main`.
