# HANDOFF — Speech-driven conversation observed; Unmute unresolved; reviewed checkpoint for hosted CI

Publication checkpoint 2026-10-02: independent Luna/max READ-ONLY review of the
latest corrected boundaries returned **READY for checkpoint**, with no confirmed
material blocker. The reviewer inspected source, pinned SDK and CI contracts;
it did not rerun tests. Root reran native **142 passed / 6 candidate skips**,
isolated candidate **6/6**, and mobile **100/100** plus typecheck. Sanitized web
export produced four routes and zero synthetic token/agent/native-import hits.
This checkpoint includes the earlier pending native/cascade work and its review
corrections. Publication is for a draft PR and hosted checks, not a merge, new
build or live trial. Hosted results belong to the PR checks; the local evidence
and earlier uncommitted/no-push labels below describe their dated operations.

Current offline checkpoint 2026-10-02 (SDD §§3/4/6/8/9/11/13): confirmed
review corrections are implemented in the reviewed publication checkpoint. The controlled cascade
launcher reserves one named job for its lifetime and now refuses SDK environment
overrides of registration/admission. An intentional protected admission record
keeps only agent/room metadata for the cutoff guard. Typed JSON parsing supports
both SDK room-field names and escaped names; unrelated SDK payloads stay scrubbed.
Native lifecycle failures log types without exception content. The installed
Google/core SDK error filters forward fresh records, preserving original records,
exceptions and cancellation. This does not protect arbitrary sinks/exporters.

Six candidate contracts now live in `backend/tests/cascade_profile`; the new
isolated lock retains 85 already-resolved runtime pins. A separate Windows CI
job checks the profile before discovery; hosted execution remains UNTESTED.
No packages were installed and existing native/foundation locks are unchanged.
Fresh native suite: **142 passed / 6 candidate-profile skips**, 203.59 s, one
existing Starlette warning. Candidate contracts: **6/6**, 23.811 s. Earlier
composition/entrypoint/launcher harnesses rerun: **8/8, 9/9, 2/2**. Outbound
denial precedes SDK imports. Initial regressions failed before fixes; two test
fixture issues found by the full run were corrected (logging cache and clock).
No actual SDK server startup, provider acceptance, room closure or playback
is established by these offline checks. An initial focused rereview was blocked
by its account usage limit; the later independent review above supersedes that
availability limitation. Root performed the regression checks reported here.

This correction pass: **53 added / 19 removed production lines**, **285 added /
1 removed test lines**, **106 added / 1 removed dependency/CI lines**; baseline
hashes validate the deltas. All edited production modules remain below 350 lines.
Existing staging, branch/HEAD, mobile, installed dependencies and unrelated work
are preserved. Source `.pyc`: zero. Browser UI, Android build and physical device:
UNTESTED. No worker, live request, token, room, phone action, commit or push.
Sarvam realtime access, Unmute and D6 remain open; no new call is authorized.
The launcher still needs the operator-owned exact-room guard/PID stop; its
timeouts request cancellation rather than guaranteeing release or a cost cap.
Prior dated evidence is in `docs/voice-cascade-compatibility.md` §§12–15.

Previous offline checkpoint 2026-10-02 (SDD §§5/6/9/10/11): native lifecycle
extraction is complete and uncommitted on `codex/voice-trial-corrections`
at unchanged HEAD `2aa5b2d`. The native worker moved from 570 to 229 lines;
common configuration, cleanup and lifecycle are 26/117/258 lines (60 net
new production lines). Native bootstrap, provider guards, PCM handling and
entrypoint behavior are preserved. Baseline backend tests: 105/105; three
new seam tests failed before extraction; final suite: 108/108 under network
denial before SDK imports. Independent Luna/max review found no material
preservation defect. This does not establish Agents 1.8.3 conformance;
direct use of the re-exported private deletion helper retains its imported
timeout default, while the production entrypoint forwards the current
native cleanup budget. Staging and unrelated work are unchanged. No worker,
provider request, phone action, build, commit or push was performed.
Unmute, Sarvam access and D6 remain unresolved; cascade integration follows
candidate AgentSession composition and log-privacy checks. Earlier entries
below are dated evidence, not this pass's process-state observations.

Latest 2026-10-01 trial: owner heard replies and held a speech-driven
conversation. One dispatch; seven completed provider turns, 108 audio
chunks / 1,388,174 bytes returned. The room cutoff deleted the room.
Owner reported an error on Unmute and return to test/permission UI; timing
and exact error remain unresolved, including whether cutoff caused it.
See `docs/device-trial-2026-10-01-conversation.md`. Earlier silence claims
below are historical. No further Start authorized; idle worker remains running.

2026-10-01 startup correction (Specification §7.1 native-audio spike):
the latest worker received two named dispatches but both failed in the
Google prerequisite check before session startup. Windows `dev` hot reload
serves jobs in a child process that bypasses the `__main__` plugin bootstrap.
The worker now defaults to `hot_reload=False`; do not enable `--watch`.
The failing task-owned worker and room guard were stopped. This correction
is offline and uncommitted; it does not establish a speech-driven reply.
Fresh offline verification: startup/voice-agent suites 45/45 passed with
network denial before SDK imports; the real default CLI bypasses the
watcher and its threaded prerequisite check succeeds. Diff check clean,
project `.pyc` count zero. No new device call was made for this correction.

Subsequent owner-run call on 2026-10-01: one dispatch, session started,
Google connection opened, 402 completed sends / 643,200 bytes, zero
returned audio chunks. Owner reported no reply. The task-owned worker
and continuous room guard were then stopped at the owner's request.
Offline investigation with network denial and the real Google serializer
confirmed the pinned beta plugin sends `mediaChunks` + `audio/pcm`, while
Google's current example uses `audio` + `audio/pcm;rate=16000` with identical
PCM bytes. Automatic activity detection is enabled by default; no disabling
configuration was found. The serialization difference is a compatibility
lead, not proof of server rejection or intelligible speech. No audio-path
fix or additional connection was made during this investigation.
Reference: https://ai.google.dev/gemini-api/docs/live-api/capabilities

2026-10-01 bounded audio compatibility correction (Specification §§6/7.1):
`voice_google_audio.py` adapts the pinned plugin's PCM `media` sends to
`audio`, adding `rate=16000` only to its bare PCM MIME type. It copies
metadata, preserves PCM byte identity, passes other input messages through,
and restores the send method before inner diagnostic cleanup. The existing
one-connection guard installs this wrapper; diagnostics count either input
field. SDK files, dependencies, mobile, and worker orchestration unchanged
in this correction. Three regression tests failed before the fix. Changes
are uncommitted; no worker startup or live connection authorized by this pass.
Verification: affected suites initially 23 passed / 1 failed (an assertion
on the old context-wrapper layout). Updated only that layout assertion;
the guard and three wire tests then passed 4/4 on the final code. Existing
privacy, cancellation, receive/cleanup, and reconnect cases passed in the
broader run. No full-suite rerun claimed. Added production/helper code:
39 lines, removed 2; new test file 81 lines plus 3 changed assertion lines
across existing tests. Diff check clean; project `.pyc` count zero.

Latest trial 2026-09-30 local time: one approved call reached the named
worker and opened a Google Live API connection. Non-silent microphone audio
reached the SDK send
path (292 completed sends, 467,200 bytes), but no provider audio returned
before the owner pressed End about 17 seconds after dispatch. The provider
receive error followed the client-initiated disconnect, so it does not
explain the earlier silence. The cutoff guard expired before Start; the
independent 60-second stop ran. An authenticated check showed no active
rooms. Post-call usage and OS mic state could not be checked directly;
the owner reported mic off. See
[device-trial-2026-09-30-60s.md](device-trial-2026-09-30-60s.md).
No repeat connection is authorized.

Previous trial 2026-09-29: a temporary PCM-level probe was prepared offline,
but the approved phone run failed before worker join because the worker's
Rustls TLS path could not access the Windows certificate store. Four
phone-only sessions appeared, all CLOSED; no PCM/provider reading was made.
Usage displayed 183 → 184 minutes, active rooms are zero, and all task-owned
services stopped. See [device-trial-2026-09-29-pcm-level.md](device-trial-2026-09-29-pcm-level.md).
That approval did not authorize a repeat connection.

Previous device trial 2026-09-29: `2aa5b2d` plus existing diagnostics and a
temporary operator greeting hook, one 23-second phone/agent room.
Google returned 14 audio chunks / 128,640 bytes and the owner heard the
greeting. The owner then spoke and waited but heard no further reply;
no additional provider audio arrived. Speech-input/turn handling remains
under investigation. Room CLOSED/empty and mic off checked; all task-owned
processes stopped. September display: 182 → 183 participant minutes and
18 → 19 sessions (rounded, not exact consumption). Evidence and limits:
[device-trial-2026-09-29-greeting.md](device-trial-2026-09-29-greeting.md).
The earlier same-day trial returned zero audio and is preserved separately:
[device-trial-2026-09-29-metadata.md](device-trial-2026-09-29-metadata.md).
The following 2026-09-28 checkpoint and older dated records are historical.

Current checkpoint 2026-09-28 (correction pass): PR #5 and PR #6 are
merged; the source baseline is `main` at `da87a84`. The confirmed findings
from the approved in-app trial below are corrected offline and locally
checkpointed on `codex/voice-trial-corrections` (not pushed). A follow-up
offline review of that pass corrected four
of its own defects before any live use:
- main-thread Google plugin init (`backend/voice_provider_bootstrap.py`,
  wired in `backend/voice_agent_dev.py` `__main__`) plus
  **registration-gated admission**: a job is refused before
  `ctx.connect()` when the plugin is missing *or* importable but
  unregistered, which is the poisoned-cache state a failed off-main-
  thread import leaves behind;
- one provider connection per session
  (`backend/voice_connection_guard.py`, plus
  `conn_options max_retry=0` for the raising path). `max_retry=0` alone
  is not a no-reconnect guarantee, so the second guard is the one that
  holds; it relies on `RealtimeSession._client` and the genai client's
  `aio.live` and must be re-verified on any SDK upgrade;
- deletion diagnostics limited to exception type plus the SDK's own
  error codes (an unrecognized value on the same attribute is dropped);
- a corrected cutoff guard (`backend/trial_cutoff_guard.py`, exact
  dispatch-name ownership, per-room deadlines) that verifies closure
  only from a successful room listing, never reads a failed or timed-out
  request as absence, keeps verifying after delayed disappearance and
  after `not_found`, caps every API call and poll sleep to the remaining
  overall budget, re-reads ownership after each listing so a room
  dispatched mid-request stays monitored, and has an operator entry
  point with a real-SDK adapter (`backend/trial_cutoff_guard_run.py`)
  whose bounded client shutdown is REPORTED as `client_close` rather
  than swallowed: exit 0 requires every owned room verified closed and
  `client_close` `ok`. Each room's delete is clamped to the budget left
  at that moment and no API call starts once it is gone. A budget is a
  request for cancellation, not a bound: a call that resists
  cancellation or never yields can outlive it and is not then reported
  as a timeout. No hard wall-clock guarantee is claimed against such
  code.
Backend `pytest backend/tests` 92/92 (5 health + 37 voice-agent + 50,
incl. fresh-subprocess real-plugin and real-SDK-boundary tests); voice
CI now runs `backend/tests`. Mobile suites untouched (96/96 remains the
2026-09-27 historical count). No worker, room, Google, or device run
in this pass. The approved in-app trial encountered the Windows
plugin-import error below, then a second phone/agent room started and
closed. The owner could not confirm an AI reply. No further Start or
worker restart is authorized. The 2026-09-28 trial record below is
preserved verbatim except where marked corrected. The 2026-09-27 offline checkpoint remains
mobile `npm test` 96/96, `tsc` clean, sanitized web export 4 routes;
those suites were not rerun during the device trial. The `feature/livekit-audio-spike`
checkpoint at `d1891ed` below (with `origin/main` at `ba4db339`, PR #2
merged, and the 78/78 count) is historical and preserved verbatim, as are
the voice-draft sections marked UNCOMMITTED — the `no push, no merge`
below described that old snapshot; PR #5 and the cross-session work are
now merged. Older statements below about untested dispatch are historical.
WebRTC is pinned exact `144.1.2`; cloud Node is pinned `22.23.2`.
Two EAS Android attempts are recorded: `5957da33` failed before the
WebRTC correction (`:livekit_react-native:compileDebugKotlin` namespace
mismatch; no APK); `9f539e50` finished with an APK for corrected source
`0c0751c`. GitHub probe `35849621938` also assembled source `0c0751c`;
its packaged APK had RECORD_AUDIO and no CAMERA. EAS artifact manifest
remains UNTESTED. APK `9f539e50` is INSTALLED on the LG Wing and
verified (dev-client launcher, Metro bundle, Home backend-ok,
SIMULATED button in both states); a one-person mic/mute/End cycle was
observed with OS-level mic release (see sections below). Received
audio and any AI conversation remain UNTESTED — the observed 2026-09-24
run was mic-only with no agent in the room, while the current Audio
Test path requests named dispatch on Start tap (observed on 2026-09-28;
an audible AI reply remains unconfirmed).
Every future build needs the
owner's separate explicit approval. CI `35844379073` is successful on
`0c0751c`. Older dated build/spike records moved verbatim to
`docs/HANDOFF-history-2026-09-24.md`.

## Approved device trial — 2026-09-28, stopped

Scope followed Specification v1.0.1 §§7.1/8 and the AGENTS free-plan gate:
one proposed Start, human End by 45 seconds, maximum 60 seconds, no retry,
with deletion of the test room approved as failure cleanup. The owner
answered "ok" after this plan and confirmed the local Google key's project
is Free tier. LiveKit Build and 179 current-month participant minutes were
checked; the project switcher listed only `call_app`, and the authenticated
room API reported zero rooms/participants before the trial. This does not
establish an exact consolidated allowance or provider charge.

- Named worker `AW_XUEQsUuW9uGS` registered at 16:24:09 IST. Its log recorded
  two dispatch requests, at 16:25:07 and 16:25:26; the exact tap count is
  unconfirmed. No agent-controlled Start or retry occurred.
- First session `RM_mNpDBbjHUWGn`: Cloud shows CLOSED, 51-second room
  duration, one participant. The worker failed before `ctx.connect()` at
  `check_trial_prerequisites()` with
  `RuntimeError: Plugins must be registered on the main thread`.
- Second session `RM_rineJh9JAGuZ`: Cloud shows CLOSED, 12-second room
  duration, two participants (`voice-spike` and agent
  `agent-AJ_KkrqtApJWupC`). Worker logs record session start at 16:25:32
  and end at 16:25:39. Both appear in the Publishers table; this is not
  proof that the owner heard a response or that the Google live handshake
  and inference completed. Owner report: first error, then two participants
  while speaking; voice delivery uncertain. Mute/Unmute were not confirmed.
- The independent room watcher was armed to request deletion at 55 seconds.
  It stopped on two unexpected simultaneous rooms before capturing one;
  its automatic cutoff was therefore NOT exercised. Immediate failure
  cleanup used the worker's exact dispatched room names as its allowlist;
  the API already reported zero rooms and zero participants, so no delete
  was issued. Both CLOSED statuses were subsequently checked in Cloud.
- Worker PID 3596 and its verified descendants (11588, 11940) were stopped.
  ADB `appops` showed the app's RECORD_AUDIO operation completed after
  11.384 seconds, with no running operation on repeated observation. The
  owner's visual microphone-indicator confirmation remains pending.
- Post-trial Usage still displayed 179 minutes and now 10 room sessions,
  versus 8 before. The unchanged rounded minute display does NOT prove
  zero consumption; exact participant-minute delta/provider usage unknown.
- Offline fresh-process reproduction: a first Google plugin import in a
  thread raises the same registration error; main-thread preload followed
  by threaded import succeeds. Installed `livekit-agents` 1.2.12 defaults
  to THREAD on Windows (`worker.py:123-127`), and plugin registration
  requires the main thread (`plugin.py:31-33`). Corrected offline in
  this pass (now locally checkpointed, see the checkpoint at the top):
  `ensure_google_plugin_initialized()` loads the optional Google
  plugin on the main thread before job threads start, retaining
  missing-plugin refusal and foundation compatibility; admission now
  also requires the plugin to be *registered*, so a job cannot slip
  through on the poisoned import cache; `backend/voice_connection_guard.py`
  caps the session at one provider connection, because the later probe
  that showed an established-session receive failure reconnecting in a
  tight loop regardless of `max_retry` (SDK-internal restart path) is
  now refused at the connection boundary rather than only bounded by
  the 120 s job deadline; deletion failures carry content-free
  diagnostics limited to recognized SDK codes; the cutoff guard tracks
  every owned room, verifies closure only from a successful listing,
  and has an operator driver. The 2026-09-28 room watcher that failed
  on two simultaneous rooms lived outside the repository; the in-repo
  guard is the corrected replacement, and the old watcher's
  extra-participant deletion heuristic was deliberately not carried
  over (ownership is exact dispatch names only).

Evidence: task logs and offline probe are in
`C:/Users/user/AppData/Local/Temp/callapp-onecall-20260928-162147/`.
The phone pre-Start screenshot shows idle/mic off/0 participants; the
post-error screenshot shows Home. Backend `/health` and Metro returned
HTTP 200; the fresh Android Metro bundle had 1,331 modules. Automated
suites and Android APK build: UNTESTED this pass. Physical device:
attempted, transport/agent join observed; audible AI reply unconfirmed.
No commit, push, package install, provider-tier change, or key disclosure.

## LiveKit quick reference — read-only audit 2026-09-28 (historical preflight snapshot)

**State: BLOCKED.** This is a stored snapshot, not approval to connect.
No LiveKit connection, worker, room, Google request, or Android build was
started for this audit. Reuse these recorded facts without revisiting the
dashboard; refresh only volatile usage and worker-registration state before
a separately authorized call.

- Project `call_app` (`p_53xwsdfy0vy`) is in European Union (Frankfurt).
  The last dashboard plan check (2026-09-25) showed Build/free; the
  2026-09-28 Overview did not display the plan. Current plan tier is
  therefore not freshly reconfirmed.
- The 2026-09-28 Overview showed 0 deployed agents and 0 concurrent agent
  sessions, with no recently deployed agents. The Agents page was empty
  and says self-hosted agents appear there too. The local process check
  found no worker. This is a snapshot; another worker could register later.
- The Usage page's Sep 1–Sep 28 local-time range showed 179 WebRTC
  participant minutes, 8 room sessions, and no agent-session-minute or
  concurrent-agent-session data. This is project usage, not an account-wide
  remaining-balance meter. Build allowances are shared across the user's
  free projects; exact account-wide remaining allowance is UNKNOWN. The
  2026-09-25 project switcher listed only `call_app`, but that does not
  establish today's account-wide totals.
- Published Build monthly allowances are 1,000 agent-session minutes,
  100,000 agent-observability events, 1,000 agent-recording minutes,
  $2.50 LiveKit Inference credit, 5,000 WebRTC participant minutes, and
  50 GB downstream transfer. Build allowances are hard caps, shared across
  free projects, reset on the first of each month, and do not roll over.
  Direct Google Gemini use is billed by Google and does not consume the
  LiveKit Inference credit. Sources:
  https://docs.livekit.io/deploy/admin/quotas-and-limits/ and
  https://livekit.com/pricing.
- Project Settings showed automatic room creation on participant join ON,
  the development token server ON, and Agent observability Enabled. The
  setting describes capture of traces, transcripts, and audio and warns
  that observability data may be stored/processed in the US. No setting was
  changed.
- The phone requests named dispatch `think-partner-dev` only in its Start
  path (`mobile/lib/voice.native.ts:399-403`); the worker uses that name
  (`backend/voice_agent_dev.py:54-57,491-494`). LiveKit assigns named
  workers only through explicit dispatch; a worker with no `agent_name`
  automatically dispatches to every new room. Source:
  https://docs.livekit.io/agents/server/agent-dispatch/.
- The worker uses direct Google model `gemini-3.8-live`
  (`backend/voice_agent_dev.py:82`) and requires `GOOGLE_API_KEY`
  (`backend/voice_agent_dev.py:120-126`). A safe variable-presence check
  found no key in process, user, or machine environment; no backend `.env`
  exists. `mobile/.env` was not opened. Google model/account access is
  UNVERIFIED; no Google request was made.
- Google's published Gemini 3.8 Live Standard rates are $0.005/min audio
  input and $0.018/min audio output on paid tier (Free Tier is listed at
  no charge). A 90-second full-duplex audio-only calculation is $0.0345
  paid-tier; this excludes text/context usage and is not a hard cost cap.
  Live API audio context accumulates. Actual tier, access, and billed usage
  remain unverified. Sources:
  https://ai.google.dev/gemini-api/docs/pricing and
  https://ai.google.dev/gemini-api/docs/live-api/best-practices.
- Bounded stop/cleanup for a later, separately approved one-call trial:
  use one Start with no retry; tap End once or let the 90-second phone
  watchdog fire (`mobile/lib/voice-session-base.ts:29`). The worker's
  active deadline is 120 seconds (`backend/voice_agent_dev.py:98`). On End
  or deadline, it closes the session with a 10-second bound, issues one
  room deletion with a 10-second bound, and calls `ctx.shutdown()`
  (`backend/voice_agent_dev.py:102,194-224,249-255`). Verify the app ended
  and the Android microphone privacy indicator is off; room deletion does
  not prove microphone release. Stop any trial worker only by its recorded
  PID after cleanup.
- **Gate:** Remains BLOCKED by unknown account-wide remaining allowance,
  no Google key in the checked environments and unverified model access,
  no worker currently listed or running, and enabled audio/transcript
  observability. Any actual LiveKit
  connection still needs separate explicit owner approval. This audit is
  not that approval.

## LiveKit Cloud account check and testing hold 2026-09-25

- Read-only Codex browser inspection of project `call_app`
  (`p_53xwsdfy0vy`): Overview, Usage, Agents, Settings > Usage and limits,
  and Billing. Project data region displayed European Union (Frankfurt);
  plan displayed Build (free). No setting was changed and no connection,
  worker, or provider call was started.
- Agents page showed no deployed agent; Overview showed 0 deployed and 0
  concurrent agent sessions. Usage for the past 7 days showed 179 WebRTC
  participant minutes, 7 room sessions, average room size 1 and average
  room duration 58 minutes. Agent session minutes had no data and the
  model section said no model usage yet. These are a dated snapshot, not
  proof that a self-hosted worker cannot appear later.
- Follow-up read-only check: Usage > This month selected Sep 1, 2026
  00:00 UTC through Sep 25, 2026 14:48 UTC. It showed the same 179
  WebRTC participant minutes, 387.51 KB downstream, 21.66 MB upstream,
  7 room sessions, and no agent-session-minute data. The account's
  project switcher listed only `call_app`. Against Build's 5,000 monthly
  WebRTC participant minutes, displayed arithmetic suggests about 4,821
  minutes unused at that snapshot. This is an estimate from rounded
  project usage, not a dedicated remaining-balance counter. Refresh the
  month-to-date view before any proposed live test.
- Usage and limits showed past-7-day peak 0/1 agents deployed, 0/5
  concurrent agent sessions, 0/100 concurrent participants, 0/2 ingress,
  0/2 egress, and 0/10,000 API requests/minute. Peak limits do not show
  remaining monthly allowance. Billing displayed 0 MB bandwidth today
  and 0 GB for September; the rounded display does not erase the usage
  figures above. No charge or future cost was inferred from those values.
- Official LiveKit docs checked 2026-09-25: the free Build plan includes
  5,000 WebRTC participant minutes, 1,000 Cloud-deployed agent session
  minutes, 50 GB downstream transfer, and $2.50 LiveKit Inference credit
  monthly. Free Build allowances are hard caps: after exhaustion, new
  requests fail instead of incurring LiveKit overage charges. Allowances
  are shared across a user's free projects, reset on the first day of
  each calendar month, and do not roll over. WebRTC media is metered by
  time/data with a 10-second session minimum. Participant minutes add
  the connected time of each human or agent participant. External
  model-provider charges are separate from LiveKit Inference credit.
  Sources: https://livekit.com/pricing,
  https://kb.livekit.io/articles/3947254704-understanding-livekit-cloud-pricing,
  https://docs.livekit.io/deploy/admin/quotas-and-limits/ and
  https://docs.livekit.io/deploy/admin/billing/.
- Owner's current rule: no LiveKit experiment until we are confident
  about the exact test's scope and cost. Before proposing any connection,
  finish offline checks; verify current plan and remaining applicable
  allowance (not just peak limits), current worker/dispatch behavior,
  external-provider eligibility/pricing if an agent can join, and a
  bounded duration, stop, and cleanup procedure. The draft Start request
  names `think-partner-dev`; an empty Agents page today does not guarantee
  an agent-free test later. A mic-only test needs a verified Start path
  that cannot dispatch the agent. LiveKit's agent-dispatch docs say a
  worker registered without `agent_name` is automatically dispatched to
  every new room, so simply removing `agentName` from the token fetch is
  not proof of an agent-free room:
  https://docs.livekit.io/agents/server/agent-dispatch/.
  If any of these checks is inconclusive,
  stay offline. This follows Prototype Specification v1.0.1 sections 7.1
  (account/plugin access) and 8 (spend control), plus the owner's stricter
  instruction. Each exact live run also needs separate explicit owner
  approval; no automatic retries, agent deployments, or plan changes.
  This account check is not approval to press Start.
- This pass: browser UI inspected as above; automated checks UNTESTED;
  Android build UNTESTED; physical-device interaction UNTESTED. Prior
  user-reported offline results are backend pytest 24/24, mobile tests
  23/23, and TypeScript clean; none was rerun in this dashboard pass.

## Fresh voice-diagnostic pre-start check 2026-09-25 (LG Wing)

- Used the already-installed `com.callapp.foundation` development-client
  APK, not Expo Go. ADB found exactly one authorized device:
  `LMF100EMW89610328` (`LM_F100`, product `winglm`). Installed package
  reports `versionName=0.0.1`, `versionCode=1`. No build, install,
  uninstall, or data clear was performed.
- Started the existing local backend and a fresh Metro dev-client bundle
  with cache clear. Metro reported Android bundle success (1328 modules);
  backend health returned HTTP 200. USB `adb reverse` was used for ports
  8000 and 8081. Port 8082 was left untouched.
- The phone loaded the current JavaScript bundle. ADB screen evidence on
  Home showed `Backend: ok (0.0.1-foundation)`, `Start simulated call`,
  and `SIMULATED UI ONLY — no microphone, no voice connection`. The
  separate Audio Test screen showed `State: idle`, `Microphone: off`,
  `Participants: 0`, and `Start audio test`.
- The agent did not press Start or initiate a LiveKit connection. No
  automated test suite or TypeScript check was run in this device pass.
  Current LiveKit account limits were unavailable; the last recorded
  account-cap screenshot is from 2026-09-24 and is historical only.
- Task-owned backend launcher/listener processes (PIDs 9900/12844) and
  Metro (PID 20384) were stopped after capture. Ports 8000, 8081, and
  8082 had no listeners afterward; no USB reverse mappings remained.
- Dev-client URL entry initially rejected the non-Expo URL form with
  `Invalid URL host: ""`; entering the development-client `exp://` URL
  over USB loaded the bundle. This was a launcher URL-format issue, not
  an app bundle error.

## Dev-client error recovery 2026-09-25 (follow-up)

- The owner reported an error after reconnecting USB. The captured
  development-launcher screen showed `Error loading app`: a connection
  attempt to its saved LAN Metro address on port 8081 timed out after
  10 seconds. No matching hard-coded host was found in mobile source
  files (environment files excluded from the search).
- At that point ports 8000 and 8081 had no listeners. Started the local
  backend and Metro with a cleared cache, added USB reverse mappings for
  ports 8000 and 8081, and verified backend health and Metro status both
  returned HTTP 200. Metro completed a fresh Android bundle (1328
  modules). No app source was changed.
- Relaunching the installed development client displayed `Loading from
  127.0.0.1:8081`. The ADB transport then disappeared before the loaded
  Home screen could be confirmed; the latest `adb devices -l` had no
  attached device. This follow-up has no LiveKit Start or mic lifecycle.
- After the owner reconnected USB, ADB found the same authorized Wing;
  USB reverse mappings were reapplied. ADB screen evidence then confirmed
  Home with backend OK and the SIMULATED label, followed by Audio Test at
  `State: idle`, `Microphone: off`, `Participants: 0`. Start remained
  untouched; the launcher timeout is resolved on the current connection.
- Backend launcher/listener PIDs 14572/8568 and Metro PID 4508 remain
  running for reconnect verification; health and Metro status are HTTP
  200. Port 8082 has no listener and was not used.

## Device smoke test 2026-09-24 (LG Wing LM-F100, Android 13)

- APK: original PC file `application-9f539e50-….apk`, 209,774,980 bytes
  (size match), ZIP integrity OK (1321 entries, `AndroidManifest.xml`
  present). No new build, no reinstall of a different file.
- `adb` via Google standalone Platform-Tools outside the repo
  (`Temp\opencode\platform-tools`, no Android Studio, no PATH change).
  Exactly one authorized device (`LMF100EMW89610328`); ~10.3 GiB free
  on `/data`; `com.callapp.foundation` absent before install.
- Install: ONE `adb install` of the original APK → `Performing
  Streamed Install / Success`, exit 0. Package present after:
  `versionName=0.0.1 versionCode=1`. No uninstall, no data deletion.
- Dev-client launcher appears (`DevLauncherActivity`), no crash
  (`AndroidRuntime` log empty). Earlier wrong-URL attempt
  (`http://192.168.31.183:8000/health` in the bundle field) gave the
  expected `Error loading app … port 8000 … after 10000ms`; corrected
  to `exp://192.168.31.183:8081`.
- Metro (dev-client/LAN, `EXPO_PUBLIC_API_URL=http://192.168.31.183:8000`,
  token-server ID unset) served the Wing: `Android Bundled 83645ms
  (1328 modules)`. JS came from `feature/livekit-audio-spike`
  (`4a672aa`); no new APK needed for the JS-only spike.
- Backend on `0.0.0.0:8000`: phone browser `GET /health 200 OK`;
  Home shows `API URL: http://192.168.31.183:8000` and
  `Backend: ok (0.0.1-foundation)`. SIMULATED button verified both
  states (`Start simulated call` / `End simulated call` + ACTIVE
  warning). Voice row: `not implemented — requires Expo development
  build (not Expo Go)`.
- Voice-test screen: owner-confirmed as-expected (needs-config,
  microphone off, 0 participants). No Start tap, no mic permission
  prompt, no LiveKit connection. Real microphone/audio, LiveKit Cloud
  connectivity, and user-to-AI conversation remain UNTESTED.
- Environment note: detached backend/Metro processes were killed
  externally three times mid-session (no shutdown lines, no reboot);
  each was restarted and re-verified. Nothing else touched
  (port 8082/Bookconnect intact).

## Voice-spike live mic test 2026-09-24 (LG Wing, dev-only token server)

Owner observations (phone screen, owner's words): audio-test screen
reached `connected`, `Microphone: live`, `Participants: 1`; mic
permission prompt appeared and was allowed; Mute showed `muted`; End
returned to the audio-test page with the `Start audio test` button.
No spoken reply heard (no agent in the room — expected).

Checks I ran (this machine, no secrets printed): owner-provided
development token-server ID placed in gitignored `mobile/.env` at the
owner's explicit instruction (existence + 51-byte size + `check-ignore`
verified, contents never opened, not in `git status`); installed
`livekit-client` contains `TokenSource.developmentTokenServer`
(SDK/code aligned); Metro log shows `env: export
EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID` and served the Wing; post-End
`dumpsys audio` shows no active recorder for
`com.callapp.foundation` (only Google HOTWORD entries) and
`appops RECORD_AUDIO: allow` — mic released at OS level; no
`AndroidRuntime` crash. Plan/usage gate was bypassed by the owner's
own Start tap before reporting dashboard numbers — owner then sent the
Project limits screenshot (2026-09-24): every limit at 0% 7-day peak
(agents 0/1, sessions 0/5, participants 0/100, egress 0/2, ingresses
0/2, API 0/10K) — concurrency headroom at that snapshot; this did not
establish total billable usage or external-provider cost.
Billing screenshot same day: plan `Build`, bandwidth today 0 MB,
September 0 GB, next invoice $0.00. Owner directive: stay
conservative — each future LiveKit connect needs its own explicit
approval; no agent deploys, no plan changes.

## One-human-to-one-AI voice path (draft 2026-09-24, UNCOMMITTED, for independent review)

Owner observations: none in this round (no live model touched).
Machine-checked only.

- Design: `backend/voice_agent_dev.py` (new) — minimal LiveKit Agents
  1.2.12 worker, `agent_name="think-partner-dev"`, Gemini Live realtime
  model via lazily-imported `livekit-plugins-google` (NOT installed —
  construction fails loudly without it). Phone passes
  `agentName` in its dev-token fetch on Start tap only
  (`mobile/lib/voice.native.ts` + `VOICE_AGENT_NAME` in
  `voice-config.ts`); SDK-verified the fetch builds the named room
  dispatch. No auto-start, fresh room per Start, worker
  `load_threshold=1.0` [superseded 2026-09-25: the worker leaves
  `load_threshold` at the SDK default with no single-job claim; a
  load value is a CPU availability signal, not admission control —
  see the dev-trial setup section below], video off, room deleted on close. Entrypoint
  failure guarantee (own code, offline-covered): post-connect model or
  session-start failure closes any partly created session (awaited
  `aclose` — coroutine in 1.2.12, source-verified) and releases the
  room connection (`shutdown`) before the
  error propagates; the success path calls neither. Single instruction
  source (`AGENT_INSTRUCTIONS`, incl. Indian English/Hinglish) feeds
  both the Agent and the realtime model; `capture_run=False` is passed
  explicitly.
- Recording/upload disables verified: no recording-call symbols in the
  file (guard test), `transcription_enabled=False,
  sync_transcription=False`, telemetry local-only (no exporter in
  1.2.12), stdlib logging with identifiers/errors only.
- Trial option (corrected 2026-09-24 — the earlier 'no confirmed
  endpoint ID' conclusion was wrong): `gemini-3.8-live`, GA per Google
  changelog 2026-09-15 ("default option for most low-latency voice
  agent experiences") with model page
  ai.google.dev/gemini-api/docs/models/gemini-3.8-live. Support at
  source/API level verified from the livekit-plugins-google==1.2.9
  wheel itself: `model` is a free string passed through to the Live
  API (`beta/realtime`, default AUDIO modalities), wheel METADATA
  requires livekit-agents>=1.2.9 (installed 1.2.12 satisfies), and the
  draft now imports the 1.2.9-correct `beta` namespace (the top-level
  path belongs to newer releases). RUNTIME model compatibility
  remains UNPROVEN without a live call. Google-published pricing was
  checked on 2026-09-25 (details below); this account's Gemini tier,
  rate limits, and actual cost are still UNKNOWN. Alternative-provider
  pricing is unverified; the owner holds neither provider key.
  LiveKit $2.50 inference credit does NOT cover external provider use.
  An earlier 2-min provider-cost estimate was unverified and must not be
  used as a budget; transport allowance and provider charges need separate
  checks before a live trial.

- Proof so far (offline only): backend pytest 21/21 (5 health + 16
  voice-agent, incl. 3 entrypoint setup-failure/success tests and
  deterministic plugin-absence/key/instruction tests via namespace
  stubs), mobile
  `npm test` 14/14 (incl. 3 new dispatch tests), `tsc` 0, web export
  4 routes with zero LiveKit SDK imports (agent name + UI strings
  only), secret scan clean, `.env` still ignored/untracked. Proves
  wiring + guards, NOT a working conversation. No server-side or
  device behavior is claimed for the worker draft.
- Trial needs separate approvals: plugin install, provider key,
  worker creds, and the Start tap itself. Steps + usage in the
   review draft, not run here. Received audio and any AI
 conversation remain UNTESTED; one participant was the local user
 only. No EAS build, reinstall, dependency, push, or merge.
- Plugin compatibility resolved 2026-09-24 (`backend/.venv` only,
  lock untouched): unconstrained dry-run wanted `pydantic→2.13.5`
  past the lock (STOPPED); constrained dry-run (`-c
  backend/requirements.lock`) selects `google-genai==2.8.0`, keeps
  `livekit-agents==1.2.12` and all 20 locked pins, adding 14 new
  packages only — installed exactly that set. Verified offline (dummy
  key, no session): real `beta.realtime.RealtimeModel` accepts the
  draft's `model`/`voice`/`instructions` kwargs, stores
  `gemini-3.8-live` verbatim for the Live API connect, defaults to
  `[AUDIO]`; wheel source confirms system-instruction + 16kHz-in /
  24kHz-out wiring, and Google docs show no 3.8 config conflict
  (no thinking params used). `pip check` clean, backend pytest 22/22
  (missing-plugin simulation still passes). Server acceptance of
  `gemini-3.8-live` and any conversation still need the live trial.

## Gemini API credential and pricing check 2026-09-25 (read-only)

- The draft worker uses direct Google Gemini API (`gemini-3.8-live`)
  through the LiveKit Google plugin. It requires `GOOGLE_API_KEY` from
  Google AI Studio for the model, separately from the LiveKit project's
  `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` for the
  worker. The mic-only phone path does not require a Google key.
  No key was created, inspected, or installed in this check.
- Google's published Gemini 3.8 Live Standard pricing lists Free Tier
  audio input and output at no charge, subject to account/model rate
  limits. Paid Tier lists audio input $0.005/min and output $0.018/min,
  plus token-priced text (including thinking output). It marks Free
  Tier data as usable to improve Google's products, Paid Tier as not.
  Verify the owner's actual project tier and active model limits in
  AI Studio before any call; LiveKit billing does not show these.
- At an illustrative INR 96/USD, paid audio input plus output for one
  full minute each is $0.023 or about INR 2.21; INR 1,000 is about
  USD 10.42 / 453 such audio-equivalent minutes. This is arithmetic,
  NOT a safe wall-clock-minute allowance: Live API re-bills accumulated
  conversation context each turn, may bill text/thinking tokens, and
  Gemini 3.8 Live bills input audio while listening. Real cost, taxes,
  currency conversion, and account availability remain unverified.
- Google says new accounts begin on a Free Tier. Paid setup in AI
  Studio requires linking billing and normally a minimum $5 prepay,
  although some accounts receive Postpay. Prepay auto-reload is
  optional; its zero-balance stop and project monthly spend caps have
  roughly 10-minute billing latency/possible overage. Neither is an
  exact INR 1,000 hard ceiling. No billing change was made.
- Sources (checked 2026-09-25):
  https://ai.google.dev/gemini-api/docs/pricing,
  https://ai.google.dev/gemini-api/docs/billing,
  https://ai.google.dev/gemini-api/docs/rate-limits,
  https://ai.google.dev/gemini-api/docs/live-api/best-practices,
  https://docs.livekit.io/agents/models/realtime/plugins/gemini/.
  FX illustration uses 2026-09-24 RBI reference USD/INR 95.9099:
  https://www.msei.in/markets/currency/historical-data/rbireferenceratearchives.

## Historical record (moved 2026-09-24 to stay under the checkpoint size limit)

Older dated sections — EAS setup, the reviewed LiveKit audio spike,
completed-work notes, foundation verification evidence, and the CI
next-action — moved verbatim to
`docs/HANDOFF-history-2026-09-24.md` (build IDs and evidence
preserved). This file stays the sole current checkpoint.

## Verify pass 2026-09-25 (pre-Start only — NO LiveKit connection made)

- `adb` (Temp platform-tools, nothing installed): exactly one authorized
  device `LMF100EMW89610328` (winglm/LM_F100); `com.callapp.foundation`
  present, `versionName=0.0.1 versionCode=1`. No install/uninstall/data-clear.
- Diff is JS/Python only (mobile/lib voice*.ts + tests, backend
  voice_agent_dev.py + test, docs); no native-dep/config change
  (package.json/app.json/eas.json/lock untouched) — installed APK reusable.
  `mobile/.env` exists and is gitignored; never opened. Code unchanged.
- LAN re-checked, not assumed: PC `192.168.31.183`, phone
  `192.168.31.150/24`. Phone ping to PC 100% loss (ICMP blocked) but
  phone `curl http://192.168.31.183:8000/health` returned
  `ok 0.0.1-foundation` — TCP path works. Ports 8000/8081/8082 free at start.
- Backend (0.0.0.0:8000, PIDs 17180/16032) and Metro (LAN 8081, Node 15192)
  started, verified (local + LAN + phone /health 200; Metro log showed
  `env: export EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID` by name only), then
  both killed externally mid-pass (no shutdown lines; same pattern as
  2026-09-24). Restart attempt (wrappers 1300/19572) also died before
  binding. Nothing of mine left running; unrelated node processes untouched.
- Misdirect evidence: one `VIEW exp://...` intent without explicit package
  opened Expo Go (`host.exp.exponent`), and Metro logged `Project is
  incompatible ... Expo Go SDK 57 vs project SDK 54`. Owner must open the
  `com.callapp.foundation` dev launcher (DevLauncherActivity confirmed
  foreground via monkey launch), NOT Expo Go. No Start tapped, no mic
  lifecycle, no AI worker touched.
- Owner accepted pre-Start evidence. The read-only LiveKit dashboard check
  is recorded above; the free-plan testing hold now applies. Explicit
  approval for a connection remains pending; no auto-retry.

## Dev-trial setup completed 2026-09-25 (offline only, UNCOMMITTED)

> Superseded by the diagnostic-correction checkpoint below (same files,
> still UNCOMMITTED): expiry is now decided by the timeout scope
> itself, session `CloseReason.ERROR` is a failure, and cancellation is
> labeled cancelled. Historical lines in this section are preserved
> unchanged.

- Worker (`backend/voice_agent_dev.py`): entrypoint refuses to join
  any room when plugin/key prerequisites are missing (checked before
  `connect`, and every refused job still calls `ctx.shutdown()`).
  Explicit dispatch only (`agent_name`); no concurrency claim
  (`load_threshold` left at SDK default). The 120 s deadline covers
  the active job only (setup awaits through wait via `asyncio.timeout`;
  synchronous model construction runs to completion and is not
  preemptible, with its time counting against the deadline at the next
  await). A Phone End closes the session itself and ends the wait
  promptly even when the agent room stays connected (session "close"
  listener registered before start); a `TimeoutError` raised by
  connect/start well before the deadline is preserved as a setup
  failure, never mistaken for expiry. Expiry, phone-End, or setup
  failure then runs one awaited, bounded cleanup outside that deadline
  (session close up to 10 s, one explicit room deletion up to 10 s
  with SDK `delete_room_on_close=False`, then `shutdown`). Total
  wall-clock can exceed 120 s by the cleanup budget. Awaited deletion
  only proves the delete call completed; phone mic release is NOT proven
  offline. Already-disconnected rooms are detected via
  `isconnected()` (no replay assumption). Audio-only input
  (`text_enabled=False`, video off, transcripts off). Verified against
  installed livekit-agents 1.2.12 (`room.on/off("disconnected")`,
  `AgentSession.on/off("close")`, explicit-dispatch `agent_name`).
  Named dispatch, SIMULATED Home button, and native-only mobile imports
  unchanged; no mobile code change in that 2026-09-25 record
  (mic release on disconnect already covered by lifecycle tests), and
  this pass likewise touches no mobile code (mobile safety findings
  deferred to the next pass).
- Reproducible deps: `backend/requirements-voice-dev.txt` (2 direct
  pins) + `backend/requirements-voice-dev.lock` (61 total pins
  (2 direct, 59 transitive), disjoint from the 20 foundation pins,
  exact match to the `pip check`-clean venv). Foundation lock untouched.
- Docs: README trial-setup section names variables only
  (`GOOGLE_API_KEY`, `LIVEKIT_URL/API_KEY/API_SECRET`); no values
  anywhere. No key created, no worker started, no room opened.
- Note: `expo export` inlines `EXPO_PUBLIC_*` values present at build
  time, so local `dist-web/` (gitignored, never committed) contains the
  dev token-server ID by name-value. Run exports without that ID in the
  environment if a clean bundle is needed; nothing was committed or pushed.
- Checks this pass: backend pytest 38/38 (33 voice incl. session-close
  prompt end + TimeoutError distinction + text-off + 5 health), mobile
  `npm test` 23/23, `tsc` clean, web export 4 routes with zero native
  LiveKit symbols, `pip check` clean. Full suite also verified with
  the plugin simulated absent (37 passed, 1 skipped); voice-only
  focused absent is 32 passed, 1 skipped. Still requires a live call:
  token fetch, dispatch, worker join, `gemini-3.8-live` server
   acceptance, actual active-deadline behavior, and any AI conversation.

## Diagnostic correction checkpoint 2026-09-26 (offline only, UNCOMMITTED)

- Worker (`backend/voice_agent_dev.py`): expiry is decided by the
  timeout scope itself (`timeout_scope.expired()`), never by comparing
  the wall clock, which gives exactly two cases. (1) `expired()` is
  false — a `TimeoutError` from connect/start (including one raised
  just before the deadline fires) is a setup failure, preserved,
  logged as such, and re-raised; the single cleanup path is unchanged
  (close/delete 10 s each + `shutdown`). (2) `expired()` is true — the
  deadline itself fired, so the call is reported as a deadline and
  ends gracefully with the time-limit reason even if connect/start
  caught the cancellation and converted it into its own
  `TimeoutError`. The scope, not the error's origin, is the sole
  authority. (The 2026-09-25 section above states case 1 only.) The
  session close event is preserved, not reduced to a string: a
  participant Phone End
  (`participant_disconnected` and other non-error reasons) stays a
  normal end, while `CloseReason.ERROR` runs the same bounded cleanup
  with reason `dev trial session error` and raises a content-free
  `RuntimeError` (reason value + error type name only, never the error
  message or conversation content). Cancellation is labeled
  `dev trial cancelled` (not setup-failed) and still propagates.
  Verified against installed livekit-agents 1.2.12
  (`CloseEvent(reason, error)` in `voice/events.py`, `emit("close",
  CloseEvent(...))` in `voice/agent_session.py`).
- Tests (`backend/tests/test_voice_agent_dev.py`): 37 voice (3 new:
  ERROR-close failure with canary-text leak check, participant-reason
  normal end, and the expired-deadline case using a REAL
  `asyncio.timeout` where connect() catches the cancellation and raises
  `TimeoutError` (asserts the deadline result and exactly-once
  cleanup); 3 cancellation expectations updated to the cancelled
  label) plus a clarified comment that the fakes run no SDK RoomIO
  (the no-second-delete half rests on `delete_room_on_close=False` plus
  the installed `room_io` source). The never-expiring-scope test is
  renamed `test_sdk_timeout_is_setup_failure_while_scope_unexpired`
  and now claims only the unexpired branch. No mobile code change in
  this pass.
- Checks this pass: backend pytest 42/42 (37 voice + 5 health), mobile
`npm test` 23/23, `tsc` clean, `pip check` clean. Still requires a
live call for everything listed in the 2026-09-25 section above.

## Pending-Start lifecycle fix 2026-09-26 (offline only, committed locally at d1891ed)

- Session (`mobile/lib/voice-session.ts`): End, background, and the
90-second watchdog now invalidate a pending Start synchronously
(generation bump + detach, no waiting for the stalled promise). A
backgrounded Start can never install even after a foreground return —
a fresh tap is required. A stalled token fetch, connection, or mic
 publication cannot stall End or the watchdog path; the orphaned run
  disposes on late settle via the existing generation/shouldAbort
  checks, so no room is ever installed behind End/background and no
  room status is displayed for a dead tap (an already-in-flight
  `room.connect` can still complete transiently at transport level,
  but the late `Connected` event is ignored and `fail()` disconnects
  it) and mic-off is attempted then, never guaranteed.
- SDK limit (installed livekit-client 2.22.3, read in `node_modules`,
not assumed): token fetch, room connect, and mic publish expose no
public cancellation — connect only has 15 s timeouts/retries for the
unreachable-server case (plus undocumented internal abort wiring, not
public API). A stalled native await cannot be stopped from JS.
- Tests: 6 new deterministic deferred-operation tests (background
then foreground return, fresh tap while the orphaned run pends, End
settling while Start is stalled, End while fetch/connect/publish each
is held). micUnconfirmed recovery, single-flight Start,
End-during-Mute, and the watchdog-as-cleanup-trigger wording
unchanged.
- Follow-up correction (same date): an orphaned run whose late disposal
rejects records `cleanupIncomplete` — a rejected end() is never proven
release, with or without the mic flag — so a waiting Start re-checks
the gate after the orphan wait instead of opening behind it, and End
routes to the retained handle. Stale "fresh Start may begin
immediately" comment corrected (fresh Starts wait for orphans).
2 more tests (unconfirmed + flag-free late-cleanup failure, each with
End retry and Start unblocked after recovery).
- Follow-up correction (same date): failed End/teardown now marks
`cleanupFailed` on the error status while the handle is retained, so
the screen shows the cleanup problem with an End retry instead of a
Start that cannot proceed — including disconnect failures where the
mic label truthfully stays off (no mic flag set). 3 more tests
(flag-free failure marker + clearing, unconfirmed marker consistency,
session End-retry-then-Start loop).
- Follow-up correction (same date, uncommitted): abort checks added
after audio configure/start so a late result can never call
`room.connect` after invalidation (2 held-stage tests proving zero
connects); failed-Start disconnect failure now returns a recovery
handle with `cleanupFailed` (no mic flag — mic stays truthfully off),
and the first End always attempts the uncertain release instead of
no-op'ing on a settled recovery handle. 3 more tests. Session/screen
need no change (existing install, gate, and End/Start wiring already
route it).
- Follow-up correction (same date, uncommitted): late mic-recovery
ownership through dispose/background (dispose attempts the retained
release before clearing it; background attempts it with no live
handle or with an unconfirmed live handle, while the pending-Start
permission-dialog case still no-ops); an unexpected-disconnect
disconnect failure now sets the same recovery flag as the fail()
path (a racing Start resolves a recovery vehicle with
`cleanupFailed` and the mic truthfully off, and End retries the
 disconnect); orphan waits abort promptly on End/watchdog/
 background/dispose with nothing opened and no second room, reporting
 pending ("Waiting for previous session cleanup.") while parked; an
 aborted wait lands the retryable abort terminal ("Start ended while
 pending...") instead of restoring a stale status. 7 more tests (3
 dispose/background ownership, 1 connect/unexpected-disconnect race,
 3 orphan-wait pending/abort). Screen needs no change (pending
 already shows End; both flags already block Start).
- Follow-up correction (same date, uncommitted): a late `Connected`
 room event after End/watchdog/background/dispose invalidation no
 longer displays a nonterminal room status for the dead tap (the
 handler now honors the same abort signal as the post-connect
 checks); `fail()` still tears the transient room down and keeps its
  terminal, with retry flags when uncertain. 2 more tests (late
  Connected after End during held connect; late Reconnecting/Reconnected
  after End while connect is in flight). No session/screen change.
- Counts this pass (historical feature-branch checkpoint — superseded
by the 96/96 count in the header; earlier dated sections are
historical): mobile `npm test` 78/78, `npx tsc --noEmit` 0,
sanitized web export 4 routes with the synthetic token-server marker
and the agent name absent (dotenv loading disabled, client-env
inlining untouched). Backend suite not rerun (worker untouched):
latest remains 42/42 (37 voice + 5 health) from the checkpoint above,
same date.

## Untested (device/runtime; compilation is recorded above)

- Android build artifact: two EAS attempts are recorded (`5957da33`
  failed before the WebRTC correction; `9f539e50` finished with an APK
  for corrected source `0c0751c`); probe `35849621938` also assembled
  source `0c0751c`. EAS artifact manifest UNTESTED (verified instead:
  `adb install` of the original APK on the LG Wing, ZIP integrity and
  package presence — see smoke-test section above).
- Physical device: PARTIAL 2026-09-24 — OBSERVED on the LG Wing: APK
  install, dev-client launcher, Metro bundle, Home backend-ok,
  SIMULATED button (both states), and a one-person mic lifecycle
  connected/live/1 → muted → End with OS-level mic release
  (owner-observed vs machine-checked kept separate in the sections
  above). Received audio and AI conversation remain UNTESTED. LiveKit
  Cloud plan/usage was inspected read-only on 2026-09-25 (see account
  check above).
- Interactive check command for the owner: run backend + `cd mobile`,
  `npx expo start --web --port 8081`, open `http://localhost:8081/`.

## Blockers / notes

- Nonblocking follow-up (2026-09-26 reviewer, not fixed here): the
  setup-failure paths in `backend/voice_agent_dev.py` use
  `logger.exception`, so a provider error's full text (not just its
  type) reaches the runtime log — inconsistent with the content-free
  discipline the session-close path already applies. No user
  conversation content can reach that path (audio-only input, and
  `session.start()` precedes any user speech), so this is a
  consistency/limits question, not a leak. Fix when convenient:
  log the error type name instead of the traceback, or state
  explicitly that error text is allowed in runtime logs. Deliberately
  NOT changed in the evidence-correction pass (runtime behavior left
  unchanged).
- Unresolved-orphan limitation (offline fake only, no device claim):
  a stalled native Start cannot be cancelled from JS, so a fresh Start
  waits for the orphan to settle. Remounting the screen (dispose + new
  session) is not a proven safe retry: an offline fake with a held
  connect showed transient two-room overlap. Keep work offline; each live
  connection still needs separate explicit approval.
- Cross-session gate + extraction checkpoint (local, offline, committed
  locally ahead of remote on `fix/cross-session-orphan-gate`): PR #5 is merged into main. Holds
  the shared cross-session gate, the `voice-session` extraction
  (`voice-shared-gate.ts`, `voice-session-base.ts`,
  `voice-session-start.ts`, each ≤350 lines), cross-session tests, and
  the extended web-boundary guard. No device, LiveKit, worker, or Google
  call. Known limits: a never-settling native Start can block later
  screens until app restart; two simultaneously live session objects are
  not globally gated, although the current single-screen flow never
  creates that state.
- Dev servers stopped after inspection; ports 8000/8081 free. Other running
  servers (port 8082, Bookconnect) belong to other work — untouched.
- One broad `Stop-Process` on `python.exe` was used mid-task; future kills
  must target PIDs/command lines only.
- Supabase: new project `zyjylsvh…` clean (0 tables); old `ahntbtkt…`
  disabled in opencode config. No migrations run or planned this milestone.
- OpenCode version on record: 1.14.33. No global permission changes made.
