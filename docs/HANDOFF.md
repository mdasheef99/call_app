# HANDOFF — review branch ready, not yet pushed

Date: 2026-09-21. Branch: `review/foundation` (local only, tracks
`origin/main`, not pushed). HEAD records the workflow-docs commit on top
of merge `fa67dd2` (parents: `origin/main` `c8930e1` README-only +
`master` `2af159e` foundation). `master` preserved untouched at `2af159e`.
Earlier states below are kept for the record.

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

## Next action — publication step (pending owner approval)

1. Done locally: `review/foundation` created from `origin/main`, `master`
   merged with `--allow-unrelated-histories`, README conflict resolved by
   keeping the developed project README (verified byte-identical to
   `master`'s), workflow docs committed separately (`f72b951`).
2. Verification on the branch: both original commits are ancestors
   (`c8930e1`, `2af159e`); diff vs `origin/main` is 29 files, +12307/-1
   (the -1 is the old `# call_app` line); no conflict markers, secrets,
   keys, or generated artifacts tracked; only `.env.example` (placeholders).
   No test rerun: the merge adds no code beyond already-verified `master`.
3. Pending: owner authorizes, then push ONLY the branch:
   `git push -u origin review/foundation`, then open a draft PR.
   Never force-push, never push `main`.
