# Device follow-up — 2026-09-28: joined, no audible reply

Source checkpoint: `62b8cf5` on `codex/voice-trial-corrections`, local only.
Scope follows Prototype Specification v1.0.1 §§7.1/8 and the AGENTS live
testing gate. Refactoring and production-code changes were not performed.

## Approval and baseline

The owner confirmed no other named or unnamed workers running elsewhere,
and previously confirmed the Google key's project is Free tier. Cloud
billing showed Build and next invoice $0.00. The project selector listed
only `call_app`; this is not an exact account-wide remaining-balance meter.

The exact proposed run was one Start, human End by 45 seconds, administrative
stop by 60 seconds, no retry, and deletion of only dispatched trial rooms
if necessary. After the preflight, the owner answered **Approve this one trial**.
Before the ready signal, the owner also reported a phone-only test. Cloud
shows three additional one-participant sessions at 17:17 UTC, all CLOSED:
`RM_R9L7X4XeyMSn`, `RM_dZ7GFtvkCGAH`, `RM_XbjZLeuj6dLp`. No worker was
running for those sessions; their exact tap count is unconfirmed.

Displayed September usage was 179 minutes / 10 sessions before those
phone-only starts, then 180 minutes / 13 sessions before the worker calls.

## Worker calls actually observed

The task-owned worker reported `PROVIDER_MAIN_THREAD_READY` and registered
as `AW_VHfk4z9bPwtd` at 17:23:16 UTC. Watch/reload was disabled. The guard
reported an authenticated baseline of zero rooms and zero participants,
then `GUARD_ARMED`. Only then was the owner given the Start signal.

| Session | Dispatch / session start UTC | Worker end UTC | Cloud result |
| --- | --- | --- | --- |
| `RM_aD2rihcZHuaU` | 17:25:58 / 17:26:03 | 17:26:16 | CLOSED, 31-second room, 2 participants |
| `RM_gsHps3J5yTWU` | 17:26:33 / 17:26:35 | 17:26:48 | CLOSED, 36-second room, 2 participants |

Exact owned rooms were `sbx-ym2qjd-XFuTFaHtGkfqGXo9MZ7QUZ` and
`sbx-ym2qjd-EaLSsU37cfvzVM5WCsMX7t`. Both dispatch records name
`think-partner-dev` and have `resuming=false`. The owner confirmed two tests
and reported no reply in either; Mute/Unmute was tried in the second.
ADB also observed the second call connected, muted, with 2 participants.

The second Start exceeded the approved one-Start scope. No agent-controlled
Start or retry was issued. Both jobs ended after participant disconnect
(`CLIENT_INITIATED`). On discovering the second dispatch, further trials
were stopped. The worker and its verified process tree were terminated.

The Windows plugin-registration failure from the earlier trial did not
recur. Session initialization and worker join are proven; Gemini handshake,
speech delivery to Gemini, returned speech, and audible playback are not
proven by a session-start log or participant count.

Cloud shows the second agent published `roomio_audio` (`audio/red`), with
63.52 KB upstream and 94.76 KB downstream. Track presence and aggregate
traffic do not establish intelligible speech or an AI response. The worker
log contains no explicit Google authentication/model rejection. Speech
timing relative to the second participant's arrival remains unconfirmed.
Post-call Android call/media streams were not muted or at zero on their
reported active routes; routing during the call was not captured.

## Cleanup and consumption

Both worker deletion attempts reported `type=ServerDisconnectedError`;
no symbolic SDK code was present. This error's cause remains unresolved.
The first guard watch independently verified its room absent through a
successful listing, reported `closure=natural`, `all_owned_closed=true`,
and `client_close=ok`. Its cutoff delete was not needed or exercised.

The guard exited after the first room closed, before the second dispatch.
**Its summary covers the first room only.** It did not supervise the second
call; closure for that call was verified separately after stopping trials.
The authenticated cleanup inspection returned `rooms=[]`; no fallback
delete was issued. Cloud independently showed both sessions CLOSED.

Worker PID 7972, child Python 10324 and console host 8516 were stopped
after PID/start-time/command verification. No task-owned worker or guard
remained on the final process check. Android AppOps showed completed
RECORD_AUDIO activity with no running operation; the last recorded interval
was 4.317 seconds. This is app-specific OS evidence, not an assertion about
other apps' microphone use. Task-created USB reverses 8000/8081 were removed;
pre-existing backend, Metro, ADB and unrelated applications were preserved.

Final Cloud usage through 17:32:50 UTC displayed **181 participant minutes,
15 sessions**: displayed +1 minute over the pre-worker baseline, +2 over
the initial preflight. Rounded/delayed counters do not establish an exact
charge or consolidated remaining allowance. Google usage was not measured.

## Evidence categories and next work

1. Browser UI: LiveKit billing, usage, project selector, Agents, sessions,
   second-call participant analytics inspected. App web preview UNTESTED.
2. Automated checks: fresh backend 92/92 before the trial; Git/diff checks
   clean and project `.pyc` count zero. Mobile 96/96 is historical, not rerun.
3. Android build: UNTESTED this pass; existing installed development client.
4. Physical device: real calls observed; no audible AI reply per owner.
   Mute/Unmute owner-reported; muted UI and completed microphone operation
   directly observed. Successful end-to-end conversation not demonstrated.

Next work is offline investigation of microphone input, provider exchange,
and phone playback, using existing evidence and content-free diagnostics.
Do not infer a cause or change production code merely from absent speech.
No further Start, worker restart, live experiment, build or push is authorized.
