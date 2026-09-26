# HANDOFF — Android first-device-build (APK 9f539e50 INSTALLED on LG Wing; one-person mic/mute/End observed 2026-09-24; received-audio/AI conversation still UNTESTED)

Current checkpoint works on `feature/livekit-audio-spike` at `d1891ed`;
`origin/main` is `ba4db339`. PR #2 merged at `15963c4` (historical EAS
base, main CI passed). The voice-draft sections below marked UNCOMMITTED
were uncommitted at the time of writing; as of this checkpoint they are
committed locally on this branch (ahead of remote, not merged) — no push,
no merge, no live claim.
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
Test path requests named dispatch on Start tap (never run live).
Every future build needs the
owner's separate explicit approval. CI `35844379073` is successful on
`0c0751c`. Older dated build/spike records moved verbatim to
`docs/HANDOFF-history-2026-09-24.md`.

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
- Counts this pass (latest voice-draft; earlier dated sections are
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
- Dev servers stopped after inspection; ports 8000/8081 free. Other running
  servers (port 8082, Bookconnect) belong to other work — untouched.
- One broad `Stop-Process` on `python.exe` was used mid-task; future kills
  must target PIDs/command lines only.
- Supabase: new project `zyjylsvh…` clean (0 tables); old `ahntbtkt…`
  disabled in opencode config. No migrations run or planned this milestone.
- OpenCode version on record: 1.14.33. No global permission changes made.
