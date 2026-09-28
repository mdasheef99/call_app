# AGENTS.md — working rules for this repo

## Current milestone: silent AI reply under investigation

Foundation (PR #1), the voice draft (PR #5), and cross-session safety work
(PR #6) are merged. The Android development client is installed, but an
end-to-end AI reply remains UNCONFIRMED. The 2026-09-28 device trial
follow-up on checkpoint `62b8cf5` reached phone-plus-agent rooms twice;
the owner heard no reply. All trial processes stopped, the authenticated
room list is empty, and the phone microphone operation ended. See
`docs/device-trial-2026-09-28-followup.md`; no further run is authorized.
The earlier trial
recorded a first-dispatch Windows plugin-import failure, followed by a
second room with the phone and agent. Both sessions are CLOSED and the
worker is stopped; another connection needs separate approval. The
offline correction pass for the confirmed findings is implemented but
locally checkpointed on `codex/voice-trial-corrections` (not pushed;
main-thread plugin init plus registration-gated admission,
one provider connection per session, cutoff guard with an operator
driver, deletion diagnostics limited to recognized SDK codes; backend
pytest 92/92) — see the latest HANDOFF checkpoint. The Expo project is
linked
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
(PR #5 and its worker merged into main): prereq refusal before connect with `shutdown()` on
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
off, text input off), covered by offline tests (counts in the section below)
— no server-side or device claim.
Cross-session work (PR #6, merged on `main` at `da87a84`) has offline
race-test evidence; the 2026-09-28 device trial did not exercise those races.
Known limits: a never-settling native Start can block later screens
until app restart; two simultaneously live session objects are not
globally gated, although the current single-screen flow never creates
that state.
The Home call button stays SIMULATED UI state; native LiveKit code must never be
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
Voice-draft (local checkpoints, offline only — historical checkpoint 2026-09-26):
backend pytest 42/42 (5 health + 37 voice-agent, per the 2026-09-26 HANDOFF
checkpoint; worker untouched since, not rerun); mobile `npm test` 78/78
(historical feature-branch checkpoint, superseded below);
`tsc` 0; sanitized web export 4 routes (synthetic token-server marker and
agent name absent).
Current offline test checkpoint 2026-09-27 (PR #6, now merged):
mobile `npm test` 96/96, `npx tsc --noEmit` clean, sanitized web export
4 routes (marker and agent name absent).
Offline correction checkpoint 2026-09-28 (local-only, backend only):
`pytest backend/tests` 92/92 (5 health + 37 voice-agent + 50 covering
main-thread provider init and registration-gated admission, start-up
ordering, the one-connection provider policy, deletion diagnostics, and
the cutoff guard with its LiveKit adapter/driver, including ownership
gained during a listing, budget-capped calls, polls and per-room
deletes, and reported client shutdown); voice CI now runs
`backend/tests`. `max_retry=0` alone is NOT a no-reconnect guarantee —
the pinned SDK reconnects an established session in a tight loop without
consulting it — so `backend/voice_connection_guard.py` caps the trial
session at one connection and must be re-verified on any SDK upgrade.
Mobile suites untouched this pass (96/96 remains the 2026-09-27
historical count).
LiveKit (`livekit-agents==1.2.12` imports on Python 3.13) is absent from
`backend/requirements.txt` / `backend/requirements.lock` (foundation-only);
it is pinned separately in `backend/requirements-voice-dev.txt` /
`backend/requirements-voice-dev.lock` for the voice-draft worker and
installed in `backend/.venv` only.

## Architectural boundaries

- Mobile talks to FastAPI; never to Supabase directly. No `service_role` key in the app.
- Native-only deps stay in `mobile/lib/*.native.ts`; web preview must bundle without them.
- Backend CORS allows local preview origins only (`localhost`/`127.0.0.1` ports 8081/19006), GET only, no wildcard.
- No Celery/Redis/Docker/WSL in this milestone; workers need Linux later.
- Supabase project for this work: `zyjylsvh…` (MCP `supabase_callapp`). The old project (`ahntbtkt…`, MCP `supabase_other`) stays disabled. Never run migrations without explicit approval, never push without approval.

## LiveKit free-plan testing gate

The `call_app` LiveKit Cloud project was last confirmed on the free Build
plan by a read-only dashboard check on 2026-09-25. The latest audit and
cleanup procedure are in `docs/HANDOFF.md` under **LiveKit quick reference
— read-only audit 2026-09-28**; reuse its static findings without repeating
dashboard visits. Its credential-availability note predates local key
provisioning. Refresh volatile allowance, credential/billing tier, and
worker-registration state only before a separately authorized run. At the
owner's direction, pause all LiveKit experiments until the exact proposed
run has a verified plan and remaining allowance, known worker/dispatch
behavior and external-provider cost, and a bounded stop/cleanup procedure.
A 0% peak concurrency reading is not proof of unused monthly allowance or
zero cost.
For a mic-only trial, prove that the Start path cannot dispatch an agent;
an empty Agents page or omission of `agentName` alone is insufficient
(unnamed LiveKit workers auto-dispatch). This gate follows the owner's
instruction and Prototype Specification v1.0.1 sections 7.1 and 8.
If any part is uncertain, keep work offline. Each live connection still
needs the owner's separate explicit approval; no automatic retries, agent
deployments, or plan changes.

Treat every connected SDK participant as metered, even with no published
audio. The 2026-09-28 audit found two overlapping September 24
`voice-spike` sessions totaling 176 participant minutes; the 143-minute
session had no publisher row. Opening Home or Audio Test without Start is
not a connection. Do not infer room closure from an ended screen, muted
microphone, phone watchdog, worker deadline, or an empty Publishers table.
The 179-minute project usage snapshot is not an account-wide remaining
balance; Build allowances are monthly and shared across free projects.

Before proposing a live trial, document one exact Start, its proposed
maximum duration, a human-operated stop timer, expected worker/dispatch,
Google billing exposure, and the fallback room-deletion procedure. Check
the current plan, current-month usage and reliable shared-allowance
headroom, active rooms/participants, and named *and unnamed* worker state.
For paid provider testing, document an explicit currency ceiling and a
way to stop further admission as required by Specification v1.0.1 §8.
If sufficient headroom or any other preflight fact cannot be established,
do not connect to find out. Record owner approval for that specific run
after presenting the preflight; approval for a completed or different run
does not authorize another connection.
Do not start a worker, fetch a live token, press Start, or create a room
while this gate is blocked.

For an approved run, allow one Start only and no retry. End within the
approved duration rather than relying on the 90-second phone watchdog or
120-second worker deadline as a hard cost cap. After End, verify the phone
mic indicator is off **and** LiveKit reports the session CLOSED, the
participant gone, and no agent/room still active; compare usage before
and after. If closure or mic release cannot be confirmed, execute the
approved cleanup procedure, stop further trials, and report the unresolved
state. This implements the spend-control gate in Prototype Specification
v1.0.1 §8; no live test may be treated as free merely because Build has
no overage charges.

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
