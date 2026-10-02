# Device trial — 2026-09-29, fixed greeting

Source: `codex/voice-trial-corrections` at `2aa5b2d`, with the existing
uncommitted diagnostics patch. Scope: Specification P12, §§6/7.1/8.
No repository production code changed for this trial. A temporary operator
hook used the installed public `AgentSession.generate_reply(user_input=...)`
once after successful startup, requesting a fixed greeting. It preserves
the original startup result and does not await or retry the speech handle.

## Approval and observed result

The owner approved with “ok proceed” after preflight: LiveKit Build, 182
September participant minutes / 18 closed sessions; no other workers or
free projects owner-confirmed; Google key project Free tier owner-confirmed.
The browser listed another project's key, so its tier was not used as proof.
One Start only; human End by 20 seconds, room cutoff at 25, app/worker stop
at 30 seconds after dispatch or earlier on duplicate dispatch; no retry,
paid request or billing change; deletion only of dispatch-proven trial rooms.

READY: 13:18:32 UTC. Cloud recorded one room, two participants:
`RM_gbBTxkJBEGbq`, room `sbx-ym2qjd-G7DugzmTvgfchJpkhAR4KP`,
13:19:40.57–13:20:03.70 UTC, 23 seconds displayed, CLOSED.
The owner heard the greeting, spoke and waited, but heard no further reply;
End was pressed and the microphone indicator was off.

## Provider evidence

One provider connection attempted/opened. Greeting requested at 13:19:42.36;
first audio returned at 13:19:43.92; model turn completed at 13:19:46.78.
Final counters: 371 calls entering plugin audio input; 379 completed audio
submissions / 606,400 bytes; **14 returned audio chunks / 128,640 bytes**.
The returned count did not increase after the greeting. No input-transcription
event was logged. Counters alone do not prove intelligible speech or a
recognized user turn; no audio, transcript or user prompt was retained.
The closing receive path reported `APIError` code `1000`, then connection
exit with `CancelledError`; this does not negate the earlier delivered audio.

## Closure and consumption

Guard: natural, verified closure; `all_owned_closed=true`, no API errors,
`client_close=ok`; no cutoff delete needed. Authenticated inspection returned
`rooms=[]`; Cloud independently showed CLOSED. Android AppOps showed no
running RECORD_AUDIO operation. The independent stop completed at 13:20:09.86.
Worker, guard, timer, backend, Metro and task-owned ADB were stopped by
verified identities. Ports 8000/8081/8082/5037 had no listeners afterwards.
The phone was no longer enumerated during USB cleanup, so explicit reverse
mapping removal was not verified; the task-owned ADB server was stopped.

September display: 182 → 183 participant minutes; 18 → 19 sessions;
22.72 MB upstream / 1.19 MB downstream. Rounded dashboard changes are not
exact per-call consumption. Google usage/cost was not independently measured.

## Read-only USB follow-up

One authorized LG Wing was inspected without starting the app or a call.
Active Android user 0 has RECORD_AUDIO permission; the denied entry belongs
to user 97, where the app is not installed. AudioService microphone mute
flags were all false, and its current mode was idle (`MODE_NORMAL`).
Retained greeting-call events show `VOICE_COMMUNICATION`, `not silenced`,
and capture-stop events; communication-mode speaker routing was also recorded.
These are configuration metadata, not audio or proof of intelligible speech.
LG's sensor-privacy dump exposes no per-sensor state, so the privacy tile
was not independently verified. Signal quality and recognized turns remain unknown.
No settings, recording, worker, Google or LiveKit action was initiated.
USB reverse mappings were empty; task-owned ADB was stopped by verified identity.
This follow-up does not authorize another live trial.

## Offline input-path investigation

Specification P03/P12 and §§6/7.1/8: no production edits or live requests.
Outbound socket/DNS denial ran before SDK imports; synthetic data only.
The guarded model, real plugin and real GenAI serializer preserved a 16 kHz
test tone and a 24→16 kHz mono test tone (peak 8,000, RMS about 5,656).
Each serialized chunk decoded to 1,600 PCM bytes. A silence fixture produced
the same 11 chunks / 17,600 bytes as the 24 kHz tone, with peak 1 / RMS 0.37
after resampling. Therefore submitted counts cannot establish audible speech.
Three signal cases passed; the native resampler subprocess also emitted an
`FfiHandle` finalizer `AssertionError` at interpreter shutdown (exit 0).
Its native shutdown was not clean; the signal assertions ran before shutdown.
A separate fake-server probe delivered a greeting turn and a second audio
turn through the receive loop, with two returned chunks and two completions,
one connection and one receive-iterator close. This is offline behavior only.
Automatic server turn detection and input transcription are requested.
The plugin sends deprecated `mediaChunks` with `audio/pcm`; the current
[Google guide](https://ai.google.dev/gemini-api/docs/live-api/capabilities#sending-audio)
uses `audio` with `audio/pcm;rate=16000`. Both forms preserve identical PCM
in the local serializer. The [API reference](https://ai.google.dev/api/live)
still documents `mediaChunks`; its rejection in this call is not established.
The missing discriminating evidence is signal level at plugin input and at
the Google-send boundary, followed by a recognized-input/turn event.
No source fix is justified yet. The speech-silence cause remains unconfirmed;
a future approved run should collect those metadata, not rely on byte counts.

## Reporting and next work

1. Browser UI: LiveKit Build/usage/closed session inspected. App web preview
   UNTESTED. Google key project tier owner-confirmed.
2. Automated checks: temporary operator proof 7/7; health/Metro HTTP 200,
   fresh Android Metro bundle 1,331 modules; final project .pyc count 0.
   Backend/mobile suites not rerun for this operator-only trial.
3. Android build: UNTESTED this pass; installed development client reused.
4. Physical device: greeting heard; subsequent speech had no audible reply;
   owner-confirmed End/mic off, OS mic completion and room closure checked.

The greeting establishes provider generation and phone playback for this
trial. Next investigate microphone PCM forwarding and user-turn detection
offline; the precise cause of speech-triggered silence remains unconfirmed.
No further live Start, worker restart, build, commit or push is authorized.
