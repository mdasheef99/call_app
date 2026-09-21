# Call App — Voice Thinking Partner (foundation milestone)

Prototype spec v1.0.1 controls v1 scope. This repo currently contains ONLY the
foundation: docs, a minimal mobile UI shell, and a minimal backend.
No auth, database, voice connection, memory, or analytics yet.

## What is in this milestone

- The 3 original specification documents (preserved, unchanged filenames).
- `mobile/` — minimal Expo + TypeScript + Expo Router app with one Home screen.
  Web preview supported for shared-UI development; web is NOT a v1 product.
  Native-only code stays in `*.native.ts` so web bundling never breaks.
  The call button is SIMULATED UI state only — no microphone, no voice.
- `backend/` — minimal FastAPI app with `GET /health` and `GET /v1/status`
  plus pytest endpoint tests. Isolated venv at `backend/.venv` (not committed).
- `mobile/eas.json` — development profile only (`developmentClient: true`,
  `distribution: internal`, Android APK). No EAS project ID linked yet;
  account login, quota, cloud build, and phone verification are pending.
- `.env.example` — local-only settings template, no secrets.
- Native audio dependencies are installed for the voice spike
  (`expo-dev-client`, `livekit-client`, `@livekit/react-native`,
  `@livekit/react-native-webrtc` + Expo plugins) but never imported: the
  call button stays SIMULATED and web preview still bundles without them.

## Compatibility decisions (locked for this milestone)

- **Mobile:** Expo SDK `54.0.37` + React Native `0.81.5` + React `19.1.0` +
  expo-router `6.0.24` + babel-preset-expo `~54.0.10` (all aligned by
  `npx expo install --fix`; `npx expo-doctor` passes 18/18). Chosen because SDK 54 is a mature release line that
  targets Android API 36, is the last line with an Old-Architecture fallback,
  and post-dates the Jan-2026 LiveKit fix confirming New-Architecture
  interop support. LiveKit React Native SDK (`@livekit/react-native` 2.x/3.x
  + `@livekit/react-native-webrtc` 144.x + `@livekit/react-native-expo-plugin`)
  is documented for Expo development builds only — its dependencies and
  native build plugins are installed and configured in this milestone,
  but application runtime code does not import or use LiveKit: the call
  button stays SIMULATED and native/device behavior remains untested.
  Target is an Expo development build, NOT Expo Go.
- **Backend:** Python `3.13.1` kept. Verified with concrete evidence (not just
  a version check): `livekit-agents==1.2.12` installs and
  `import livekit.agents` succeeds inside the isolated `backend/.venv`.
  Committed `backend/requirements.txt` records the direct dependency pins
  and stays foundation-only (fastapi, uvicorn, pydantic, httpx, pytest);
  `backend/requirements.lock` is the fully pinned set used for installation
  and CI. LiveKit stays out of both until the voice milestone.
- **Android toolchain mapping (for the chosen SDK 54 / RN 0.81 line):**
  compileSdk 36, targetSdk 36, Android Gradle Plugin 8.x (requires JDK 17),
  Gradle 8.10+, Node 20.19+ (we use 22.13.0). Android Studio ships a bundled
  JDK (its `jbr/` directory) that can run Gradle as well as the IDE: select
  it in Studio under Settings > Build Tools > Gradle, or point `JAVA_HOME`
  / `org.gradle.java.home` at it for command-line builds. Either way the
  JDK running Gradle must be 17+ (NOT the Java 8 currently on this machine).
  Exact versions are confirmed at install time by `npx expo-doctor` and the
  generated `android/` project (created only when prebuilding).
- **Celery workers:** will need a supported Linux environment later
  (matching production). Not configured here — no Celery, Redis, Docker,
  or WSL in this milestone by design.

## Prerequisites (Windows PowerShell)

- Node 22 + npm (this machine: Node v22.13.0, npm 10.9.2). Use the local
  Expo CLI via `npx expo`, NOT the legacy global `expo-cli`.
- Python 3.13 (this machine: 3.13.1) with `venv`.
- No Android Studio needed for this milestone (web preview + tests only).

## Setup and run

```powershell
# 1) Backend — create env, install, test, run
python -m venv backend\.venv
& ".\backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.lock
& ".\backend\.venv\Scripts\python.exe" -m pytest backend\tests -q
& ".\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# 2) Mobile — install, typecheck, web preview (needs backend running for "ok")
cd mobile
npm install
npx tsc --noEmit
npx expo start --web
```

Copy `.env.example` to `mobile/.env` for local tweaks (never commit `.env`).
Backend host/port are passed explicitly as `uvicorn` CLI flags below;
no backend environment variables are consumed in this milestone.

## How a physical phone reaches the local backend

Phones cannot use `localhost` — that means the phone itself. The phone must
use your computer's LAN address, on the same Wi-Fi, with Windows Firewall
allowing the port:

1. On the computer: find the LAN IPv4 (PowerShell: `ipconfig`, look for
   `IPv4 Address`, e.g. `192.168.1.23`).
2. From the repository root, start the backend on all interfaces using the
   project's Python environment:
   `.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000`.
   (Local-only verification instead uses `--host 127.0.0.1`.)
3. On the same Wi-Fi, set the phone's URL to
   `EXPO_PUBLIC_API_URL=http://192.168.1.23:8000` (your IP, not localhost).
4. Verify from the phone browser first: `http://192.168.1.23:8000/health`
   should return `{"status":"ok",...}` before testing the app.

## Android: local build vs EAS cloud development build

This computer has 8 GB RAM (~1.3 GB free during inspection) and ~25 GB free
disk. A full local Android build needs Android Studio + SDK + JDK 17 (~8 GB),
Gradle caches, and RAM headroom — workable but tight, and emulators/system
images are NOT recommended here (prefer your physical phone).

- **Local build (free, no account):** install Android Studio (includes SDK,
  platform-tools/adb, bundled JDK 17), accept licenses, set `ANDROID_HOME`,
  connect the phone via USB with USB debugging. Guide:
  https://developer.android.com/studio/install and
  https://docs.expo.dev/get-started/set-up-your-environment/
  Verify with: `adb devices` (phone listed), then `npx expo run:android`
  or `npx expo-doctor`. Cost: disk/RAM/time on this machine.
- **EAS cloud development build (recommended for this machine):**
  Expo builds the native binary on their servers; you install the resulting
  APK on your phone. Requires: a free Expo account
  (https://expo.dev/signup), `eas-cli`, `eas login`, `eas build:configure`,
  then `eas build --profile development --platform android`.
  Free-tier build minutes/quotas apply (see https://expo.dev/pricing);
  internal distribution works without the Play Store. Needs network to
  download the APK to the phone.

Recommendation: use the EAS cloud development build for the native-audio
spike (agreed stack decision), and keep this machine for web preview, tests,
and backend work. Do NOT start paid plans without explicit approval.
Expo Go will NOT work for native audio — development build only.

## Verification status (this milestone)

Tested code revision: `9167a74` plus the uncommitted corrections in this
round (CORS regression tests, lockfile BOM removal, doc fixes).

- Checks rerun now: `pytest backend/tests` 5 passed;
  `npx tsc --noEmit` exit 0; `npx expo-doctor` 18/18 (see HANDOFF for
  dates and the web-export result).
- Earlier implementation browser inspection (2026-09-20, backend live):
  Home rendered, `Backend: ok (0.0.1-foundation)`, simulated-call toggle
  worked, 0 console errors (1 framework `pointerEvents` deprecation
  warning). Not rerun in this correction round.
- Independent reviewers' checks at `9167a74`: pytest 3 passed, `tsc`
  exit 0, `expo-doctor` 18/18, live `GET /health` returned
  `{"status":"ok",...}` on an unused test port. Reviewer runs, not a
  substitute for the checks above.
- Android build completed: UNTESTED — blocked, no Android Studio/SDK/adb
  on this machine (by design in this milestone).
- Physical-device behavior tested: UNTESTED — no device connected, no voice
  implemented (simulated UI states only, labelled as such).
