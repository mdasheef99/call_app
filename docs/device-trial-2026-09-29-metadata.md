# Device trial — 2026-09-29, provider metadata

Source: `codex/voice-trial-corrections` at `2aa5b2d`, with the existing
uncommitted diagnostics patch. Scope: Prototype Specification v1.0.1
P12, §§6/7.1/8. No production code changed during this trial.

## Approval and actual call

Preflight: LiveKit Build, September display 182 participant minutes / 17
sessions, authenticated rooms empty; Google project Free tier. The owner
confirmed no other workers or free projects and approved one Start,
human End by 45 seconds, room cutoff at 55, app/worker stop at 60 or on
duplicate dispatch, no retry, and deletion of only dispatch-proven rooms.
The first preparation window expired without any dispatch or phone Start;
its stop process terminated the worker/app. Fresh controls were armed for
the same approved call, with another authenticated empty-room baseline.

READY was given at 12:31:30 UTC. Cloud records one room, two participants:
`RM_JJreer67FYia`, room `sbx-ym2qjd-Y5Rqe8Z6fZu6YHv74fWnbJ`,
12:31:57.54–12:32:19.25 UTC (21 seconds displayed). The owner reported
**no reply; End pressed; microphone indicator off**. No retry occurred.

## Provider evidence and limits

One provider connection attempted and opened. Final counters: 345 calls
entering plugin audio input; 353 completed audio submissions, 564,800
bytes; **0 returned audio chunks / bytes**. No input-transcription or
model-turn-complete event was recorded. No audio or text was retained.
These counters do not prove intelligible speech, server acknowledgement,
user-turn detection, or model acceptance. Context entry is not a successful
conversation. The receive path reported `APIError`, code `1000`, then
connection exit with `CancelledError`. The installed genai SDK translates
WebSocket close codes into APIError; 1000 alone does not establish an
authentication, quota, or model-rejection cause. Root cause remains open.

## Closure and consumption

The guard reported natural, verified closure of the exact room,
`all_owned_closed=true`, no API errors, `client_close=ok`; no cutoff delete
was needed. Authenticated room inspection returned `rooms=[]`. Cloud
independently showed CLOSED. Android AppOps showed no running RECORD_AUDIO
operation after End/app stop. All task-owned worker, guard, timer, backend,
Metro and ADB processes stopped; task USB reverses removed; ports
8000/8081/8082 had no listeners on the final check.

September display after the call: 182 participant minutes / 18 sessions,
22.56 MB upstream / 1.02 MB downstream. The unchanged rounded minute
display does not mean zero consumption; Google usage/cost was not measured.

## Reporting and next work

1. Browser UI: LiveKit billing/usage/session closure and Google project tier
   inspected. App browser preview UNTESTED.
2. Automated checks: health/Metro preflight and Git checks performed;
   backend 101/101 was verified before this trial, not rerun during it;
   mobile 96/96 remains historical. Final project .pyc count 0.
3. Android build: UNTESTED this pass; existing development-client APK used.
4. Physical device: one real phone/agent call, owner-confirmed no audible
   reply and mic off; OS mic completion and room closure checked.

Next: inspect submitted PCM format and speech/turn handling offline before
changing behavior. The absence of returned provider audio places this
call's silence before phone playback; it does not identify the underlying
cause. No further Start, worker restart, build, commit or push is authorized.
