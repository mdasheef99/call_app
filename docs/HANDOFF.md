# HANDOFF — Android first-device-build (one build submitted and failed; correction pending review)

PR #2 merged at `15963c4` (main CI passed). This round works on
`feature/android-first-device-build`, based at `origin/main` `15963c4`.
One EAS Android development build was submitted and failed
(`5957da33`, `:livekit_react-native:compileDebugKotlin` namespace
mismatch); no APK was produced. The WebRTC correction (exact
`144.1.2`) is applied and reviewed at source/config level only — it
has not been compiled or device-tested. No second build is authorized;
every future build needs the owner's separate explicit approval.
Build allowance consumed: 1 Android build on the $0 Free plan (no
charge implied or evidenced). No voice work. Pre-merge status below
is historical.

## EAS setup (this round, uncommitted)

- Tooling: local Node `22.13.0`; `eas-cli@24.7.0` requires
  `^20.18.3 || >=22.0.0` (satisfied; versioned `npx` invocation, no
  global install). Cloud image default is Node `20.19.4` (official infra
  docs); `machina@7.0.1` requires `>=22.22`.
- Cloud pin: `mobile/eas.json` development profile sets exact
  `"node": "22.23.2"` — latest Node 22 release verified in the official
  release index (nodejs.org, 2026-07-28; SHASUMS index HTTP 200),
  satisfying `>=22.22` on the Node 22 line. Supported by the documented
  eas.json `node` profile field. No local Node or dependency changes.
- Local (22.13.0) vs cloud (22.23.2): same major; cloud is minor/patch
  ahead. Both satisfy eas-cli and Expo SDK 54 (`Node 20.19+`). Cloud
  `npm install` should no longer raise the machina EBADENGINE warning;
  local installs still warn (harmless, non-blocking — demonstrated).
  Cross-version bundler drift is possible in principle; actual cloud
  compatibility is proven only by the build itself (UNTESTED).
- Expo identity: `whoami` → `mdasheef` (verified post-login; credentials
  never in chat). Project **created** (status `created`, not linked —
  no duplicate): `@mdasheef/call-app-foundation`, ID
  `4104833e-c58d-48b7-91b2-9bbbd373875d`,
  https://expo.dev/accounts/mdasheef/projects/call-app-foundation.
  Slug and Android package preserved. Allowance verified from owner
  dashboard screenshots: Free plan ($0/month), 15 Android + 15 iOS
  builds; usage was 0/30 at setup, then 1 Android build consumed by
  `5957da33` (failed, no APK; $0 plan — no charge implied or evidenced).
- `project:init` rewrote `app.json` beyond linkage: it materialized the
  webrtc plugin's 8 permissions into static `android.permissions`
  (including CAMERA) and added `owner`/`extra.eas.projectId`.
  Post-link introspect re-verified: `blockedPermissions` still strips
  CAMERA from the resolved list, audio permissions preserved, manifest
  preview still carries CAMERA with `tools:node="remove"`. Behavior
  unchanged; final APK manifest still UNTESTED.
- Preflight (Free-plan budget amendment, all local, zero builds
  consumed — `build:list` returns `[]`): init rewrite inspected
  (linkage + materialized perms only); `expo install --check` clean and
  `expo-doctor` 18/18 re-run post-link; prebuild config resolves;
  `build:inspect archive` shows upload is 60 files / 0.7 MB with no
  `node_modules`, `dist-web`, `.env`, keystores, or secrets (only
  `.env.example` template); local `expo prebuild --platform android`
  generated a manifest with CAMERA `tools:node="remove"`, audio perms
  present, `newArchEnabled=true`, `hermesEnabled=true`, namespace
  `com.callapp.foundation` — generated `android/` removed and the
  tool-added `ios` npm script reverted afterwards (tree verified clean
  apart from the three intended files). `build:inspect pre-build`
  gave inconsistent empty output (`Build failed` once, then silent);
  not pursued further to protect the budget — recorded, non-blocking.
- Build attempt (ONE authorized, Free plan): submitted
  `5957da33-7fc0-4a8e-a1de-544e3b15242e` (created 2026-09-22T05:53:06Z,
  development/Android). Keystore auto-provisioned in cloud, upload
  296 KB, fingerprint computed. Status: **ERRORED** (completed
  05:56:30Z, ~3.5 min) — failing phase **"Run gradlew"**, message
  "Gradle build failed with unknown error", no artifacts. Phase logs
  are dashboard-only:
  https://expo.dev/accounts/mdasheef/projects/call-app-foundation/builds/5957da33-7fc0-4a8e-a1de-544e3b15242e#run-gradlew.
  No retry/resubmit per budget amendment. Allowance consumed: 1 Android
  build (was 0/30).
- Diagnosis (read-only, via CLI `logFiles` reference; signed URL
  redacted; Brotli payload decoded locally): failing task
  `:livekit_react-native:compileDebugKotlin`, 18 errors, all
  `org.webrtc` ↔ `livekit.org.webrtc` type mismatches (e.g.
  `CustomVideoDecoderFactory.kt:50` expected `org.webrtc.VideoDecoder?`,
  actual `livekit.org.webrtc.VideoDecoder?`). Root cause confirmed:
  `144.2.0` depends on `io.github.webrtc-sdk:android-prefixed`
  (relocated namespace) while `@livekit/react-native@2.12.0` Kotlin
  imports unprefixed `org.webrtc.*`; published `144.1.2` tarball
  verified to depend on unprefixed `io.github.webrtc-sdk:android`.
- Correction (this round, uncommitted): `@livekit/react-native-webrtc`
  pinned exact `144.1.2` (`mobile/package.json:17`); lockfile updated
  by normal `npm install` (8-line diff, webrtc entry only).
  `@livekit/react-native` stays `2.12.0`. Installed `144.1.2` verified:
  gradle dep is unprefixed `android:144.7559.05`, no `livekit/` java
  sources, proxies import `org.webrtc.*`. Peers satisfied (`^144.1.2`,
  `livekit-client ^2.19.0` vs `2.22.3`; `npm ls` clean, single
  versions). Checks: `install --check` clean, `expo-doctor` 18/18,
  `tsc` exit 0, web export 3 routes, introspect shows owner/projectId,
  block, audio perms, and CAMERA `tools:node="remove"` intact.
  The namespace mismatch is addressed only insofar as inspection
  proves alignment — native compilation and phone behavior remain
  UNVERIFIED. No second build submitted.
- Next action: focused review of this correction (uncommitted,
  unpushed). Any second build needs the owner's separate explicit
  approval after reviewing the exact candidate and evidence.

## Completed work (this round)

- Installed via `npx expo install` (no force, no upgrades):
  `expo-dev-client ~6.0.21`, `livekit-client ^2.22.3`,
  `@livekit/react-native ^2.12.0`,
  `@livekit/react-native-expo-plugin ^1.0.2`,
  `@livekit/react-native-webrtc ^144.2.0`,
  `@config-plugins/react-native-webrtc 13.0.0` (pinned: latest 15.x needs
  Expo >= 56, 14.x needs Expo ^55; 13.x needs Expo ^54 — verified from
  peer metadata, not guessed).
- `app.json`: LiveKit plugins added; package ID, router, New Architecture
  preserved. Camera is excluded from v1, so `android.blockedPermissions`
  is set to `["android.permission.CAMERA"]` (omission from
  `android.permissions` alone was a no-op: the webrtc plugin re-adds
  CAMERA at prebuild via `withWebRTC.js`). Introspect verifies the
  documented interaction: CAMERA is gone from the resolved
  `android.permissions` list, audio permissions (`RECORD_AUDIO`,
  `MODIFY_AUDIO_SETTINGS`, `BLUETOOTH`) are preserved, and the merged
  manifest preview carries the CAMERA entry with `tools:node="remove"`.
  That marker is a removal instruction, not proof of the final APK
  manifest — merged-APK verification stays UNTESTED. No camera code
  runs anywhere. Machina Node-engine mismatch (`machina@7.0.1` via
  `livekit-client@2.22.3` requires Node `>=22.22`; this machine has
  22.13.0) stays recorded as an unresolved compatibility risk for EAS
  environment selection; no Node/dependency upgrades in this round.
- `mobile/eas.json`: development profile only, no owner/project ID.
- Verified: `expo install --check` clean, `expo-doctor` 18/18, `tsc`
  exit 0, prebuild config resolves, web export 3 routes with native
  excluded. Doctor count is current evidence, not a fixed target.
- Independent review and focused correction verification (fresh session,
  working tree inspected directly): prior findings closed, no new issues.
  Android compilation, final APK manifest, and physical-device behavior
  remain UNTESTED (see Untested below).
- Prior rounds below are kept for the record.

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

## Verification evidence (historical — foundation round at `9167a74`, not checks of `15963c4`)

Current branch/base: `feature/android-first-device-build` at `15963c4`
(`origin/main`). The paragraphs below record the foundation round on
top of `9167a74` and are preserved unchanged as historical evidence.

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

## Next action — CI review (pending)

1. Done: `review/foundation` pushed at `5a91ab9`. This round adds minimal
   CI (`.github/workflows/ci.yml`: backend py3.13 + lockfile + pytest;
   mobile node22 + `npm ci` + typecheck + web export), aligns README/AGENTS
   install lines with the lockfile, fixes the stale test count (5).
2. Pending: owner reviews the CI commit; push the branch again; open a
   draft PR. Hosted Actions execution is unproven until it runs — a local
   workflow file is not proof of green CI.
