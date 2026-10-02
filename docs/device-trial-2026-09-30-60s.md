# Device trial — 2026-09-30 local time, one-minute cap

Source: `codex/voice-trial-corrections` at `2aa5b2d`, existing uncommitted
diagnostics, and temporary operator scripts outside the repository. No APK,
dependency, plan, or production-code change. This is an observation, not a
working-conversation claim.

The owner approved one new connection after preflight under Prototype
Specification v1.0.1 §8's verification and spend-control gate: LiveKit Build with
184 displayed September participant minutes, zero active rooms, LG Wing
connected, and the owner's confirmation that the Google key project is on
Free tier. [Google's pricing page](https://ai.google.dev/gemini-api/docs/pricing)
lists `gemini-3.8-live` Free-tier input and output as free.
The plan was one Start, human End by 45 seconds, room cutoff at 55 seconds,
and independent app/worker stop at 60 seconds after dispatch, with no retry.

The phone showed Audio Test idle, mic off, zero participants before Start.
The named worker registered and received one dispatch at 18:05:44 UTC on
2026-09-29. The process-local certifi CA bundle let the worker join; the
previous Windows native-certificate-store failure did not recur. The
provider connection opened at 18:05:47 UTC. Diagnostics recorded 284 calls
entering the plugin input wrapper and 292 completed SDK audio-send calls
(467,200 bytes). PCM levels at the plugin input and pre-submit send seams
were non-silent, with peaks up to 27,969. These counters do not prove that
Google accepted an audio turn or that the phone would have played a response.
No provider audio chunk returned in this call. The worker logged a
client-initiated phone disconnect at 18:06:00.778 UTC, about 17 seconds
after dispatch. Its `receive_failed` diagnostic (`APIError`, code 1000)
followed at 18:06:00.885 UTC; it cannot be assigned as the cause of the
earlier silence. The pinned google-genai `live.py` wraps WebSocket close
code 1000 (normal closure) as `APIError`, consistent with phone-End cleanup.
The owner reported no reply and microphone indicator off.
The existing diagnostics emitted no input-transcription or turn-complete
event before End. PCM was near-silent for two seconds, then rose again;
that trace does not establish whether server-side voice activity detection
ever finalized an utterance. [Google's Live API guide](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
says automatic VAD responds after detecting the end of speech. A longer
silent wait after one short utterance is the next discriminating device
test, requiring its own approval; increasing the maximum duration alone
would not diagnose turn handling.

The cutoff guard started with a 90-second overall wait about 106 seconds
before dispatch, so it expired before Start. It
reported `deadline_exceeded=true` with no owned rooms, so the proposed
55-second room cutoff was **not active** during the call. The independent
stop recognized the single dispatch and ran 60 seconds later, stopping
the worker and app. An authenticated room-list check after cleanup returned
zero active rooms. Worker deletion logged `ServerDisconnectedError`; the
empty room list proves no room remained active, not that deletion succeeded.
Backend and Metro were stopped by their recorded PIDs; USB reverse mappings
were removed; port 8082 was untouched. ADB could not recheck AppOps after
the phone disconnected from USB. The post-call LiveKit Usage page could not
be opened because Codex automatic approval review hit an account usage
limit, so the participant-minute delta is UNVERIFIED. The temporary
launcher now requests a 300-second overall guard wait, allowing up to
125 seconds of setup before the independent stop's 120-second no-dispatch
window and the 55-second per-room cutoff. The operator must check that
setup has not exhausted that margin before declaring READY. This is an
offline-only correction, unproved live. No new trial is authorized.

1. Browser UI: preflight LiveKit Billing/Usage inspected; post-call usage
   UNTESTED because browser approval review rejected navigation.
2. Automated checks: offline SDK import with CA bundle and operator syntax
   passed; backend health 200 and Metro running. Test suites UNTESTED this run.
3. Android build: UNTESTED; installed development client reused.
4. Physical device: Audio Test pre-Start inspected; owner heard no reply and
   reported mic off after End. Post-call AppOps UNTESTED (USB disconnected).
