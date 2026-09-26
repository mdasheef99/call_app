# Call App — Voice Thinking Partner (foundation + voice-draft checkpoints)

Prototype spec v1.0.1 controls v1 scope. The committed foundation is docs,
a minimal mobile UI shell, and a minimal backend. No auth, database, memory,
or analytics. The voice draft is committed as local checkpoints on
`feature/livekit-audio-spike` (ahead of remote, not merged, offline only,
for independent review): a native LiveKit audio spike — mic publish,
90-second watchdog, End during a pending Start, orphan gating, truthful
mic/cleanup status with End retry — plus a dev-only voice-agent worker.
No live call made; no device claim.

## What is in this milestone

- The 3 original specification documents (preserved, unchanged filenames).
- `mobile/` — minimal Expo + TypeScript + Expo Router app with one Home screen.
  Web preview supported for shared-UI development; web is NOT a v1 product.
  Native-only code stays in `*.native.ts` so web bundling never breaks.
  The call button is SIMULATED UI state only — no microphone, no voice.
- `backend/` — minimal FastAPI app with `GET /health` and `GET /v1/status`
  plus pytest endpoint tests. Isolated venv at `backend/.venv` (not committed).
- `mobile/eas.json` — development profile only (`developmentClient: true`,
  `distribution: internal`, Android APK, cloud Node `22.23.2`). Linked to
  `@mdasheef/call-app-foundation` (owner `mdasheef`). WebRTC is pinned
  exact `144.1.2`. Two EAS Android attempts are recorded: `5957da33`
  failed before the WebRTC correction (Gradle `:livekit_react-native`
  namespace mismatch; no APK); `9f539e50` finished with an APK for
  corrected source `0c0751c`. GitHub probe `35849621938` also assembled
   source `0c0751c`; its packaged APK had RECORD_AUDIO and no CAMERA. EAS
   artifact manifest remains UNTESTED. APK `9f539e50` is installed on the
   LG Wing (dev-client launcher, Metro bundle, Home backend-ok,
   SIMULATED button verified) and a one-person mic/mute/End cycle was
   observed; received audio and any AI conversation remain UNTESTED.
   Every future build needs the owner's separate explicit approval.
- `.env.example` — local-only settings template, no secrets.
- Native audio dependencies are installed for the voice spike
  (`expo-dev-client`, `livekit-client`, `@livekit/react-native`,
  `@livekit/react-native-webrtc` + Expo plugins) but only the Audio Test
  spike imports them (`mobile/lib/voice.native.ts`, never shared/web
  code): the Home call button stays SIMULATED and web preview still
  bundles without them.

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
  but only the Audio Test spike imports and uses LiveKit at runtime
  (`mobile/lib/voice.native.ts`): the Home call button stays SIMULATED
  and native/device behavior remains untested.
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

## Voice-trial setup (development only, local checkpoint review draft)

One-human-to-one-AI trial path: `backend/voice_agent_dev.py` worker +
mobile Audio Test screen, which requests named dispatch
`think-partner-dev` in its token fetch on Start tap (verified offline;
no live dispatch has ever run).
The Home call button stays SIMULATED; native LiveKit imports stay in
`mobile/lib/*.native.ts` (never in shared/web code).

```powershell
# Trial worker deps (separate approval to install; never in requirements.lock)
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock -r backend\requirements-voice-dev.lock
```

Trial-shell variables (names only — values are never committed, never
printed, never placed in the app):
`GOOGLE_API_KEY` (Gemini API key),
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (worker creds).
The worker refuses to join any room when plugin or key is missing
(checked before connect, and every refused job still calls
`ctx.shutdown()`); the worker is explicit-dispatch only with no
concurrency claim. The 120-second deadline covers the active job
only (setup awaits through wait; slow awaits are interrupted, but
synchronous model construction runs to completion and is not
preemptible by `asyncio.timeout`, with its time counting against the
deadline at the next await): a Phone End closes the session itself
and ends the wait promptly even when the agent room stays connected,
and a `TimeoutError` raised by connect/start is preserved as a setup
failure while the timeout scope is unexpired — expiry is decided by
the scope itself, never by comparing the clock. Once the scope HAS
expired the call is reported as a deadline and ends gracefully, even
if connect/start caught the cancellation and converted it into a
`TimeoutError` of its own. A
session close carrying `CloseReason.ERROR` is a failure (content-free
reason + error-type metadata) that raises instead of reporting a
successful end; cancellation is labeled cancelled and still
propagates.
On expiry, phone-End, session error, cancellation, or setup failure the worker then runs one
awaited, bounded cleanup outside that deadline (session close up to
10 s, one explicit room deletion up to 10 s with SDK auto-delete
disabled, then `shutdown`). Total wall-clock can exceed 120 s by the
cleanup budget; awaited deletion only proves the delete call
completed and does not prove phone mic release. Text input is
disabled (`text_enabled=False`) for this audio-only worker.
Run only with separate approvals for plugin install, provider key,
worker creds, and the Start tap; each live connection needs the
owner's explicit approval. Provider billing is separate from LiveKit
allowance (see HANDOFF); no charge is implied by running offline tests.

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

Tested code revision: `0c0751c`.

- CI `35844379073` successful on `0c0751c`: backend pytest 5 passed;
  mobile `npm ci` + `tsc --noEmit` + web export passed.
- Historical (foundation round at `9167a74`, preserved): `pytest
  backend/tests` 5 passed; `npx tsc --noEmit` exit 0;
  `npx expo-doctor` 18/18; web export 3 routes.
- Earlier implementation browser inspection (2026-09-20, backend live):
  Home rendered, `Backend: ok (0.0.1-foundation)`, simulated-call toggle
  worked, 0 console errors (1 framework `pointerEvents` deprecation
  warning). Not rerun in this correction round.
- Independent reviewers' checks at `9167a74`: pytest 3 passed, `tsc`
  exit 0, `expo-doctor` 18/18, live `GET /health` returned
  `{"status":"ok",...}` on an unused test port. Reviewer runs, not a
  substitute for the checks above. Historical; CI above is the current
  record for `0c0751c`.
- Android build completed: two EAS Android attempts are recorded —
  `5957da33` failed before the WebRTC correction; `9f539e50` finished
  with an APK for corrected source `0c0751c` (see HANDOFF). GitHub probe
  `35849621938` also assembled source `0c0751c`; its packaged APK had
  RECORD_AUDIO and no CAMERA. EAS artifact manifest remains UNTESTED.
  APK `9f539e50` was installed on the LG Wing via standalone
  platform-tools outside the repo; install verified, no local Android
  Studio/SDK (by design).
- Physical-device behavior tested: PARTIAL 2026-09-24 — install,
  dev-client launcher, Metro bundle, Home backend-ok, SIMULATED button
  (both states), and a one-person mic/mute/End cycle with OS-level mic
  release observed (see HANDOFF). Received audio and any AI conversation
  remain UNTESTED; the spike so far is mic-only with no agent.
