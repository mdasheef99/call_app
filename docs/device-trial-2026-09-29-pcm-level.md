# Device trial — 2026-09-29, PCM-level probe blocked before worker join

Source: `codex/voice-trial-corrections` at `2aa5b2d` plus the existing
uncommitted diagnostics. Temporary operator scripts and logs are outside the
repository; no production code, dependency, APK, or plan changed.

The owner approved one diagnostic Start after preflight: LiveKit Build,
183 displayed September participant minutes, 19 sessions, zero active rooms
or participants, no local worker, and the owner's earlier confirmation of
no other workers/free projects and a Google Free-tier key project. The LG
Wing development client was loaded over USB; Audio Test showed idle,
microphone off, zero participants. The approved bounds were human End by
20 seconds, room cutoff at 25 seconds, independent app/worker stop at
30 seconds after dispatch, and no retry.

The worker accepted one named dispatch, but its LiveKit RTC connection
failed before joining: Rustls could not open the Windows current-user
certificate store (access denied), then reported no native root CAs and
an unknown issuer. A second dispatch arrived; the independent stop
detected two owned rooms and killed the worker/force-stopped the app.
There were **zero `voice_pcm_level` records and no provider connection
evidence**. The speech-level question remains untested by this run.

Cloud later recorded four one-participant rooms in this window, all CLOSED:
[first](https://cloud.livekit.io/projects/p_53xwsdfy0vy/sessions/RM_o9eFZNHxHGAE)
(5 s), [second](https://cloud.livekit.io/projects/p_53xwsdfy0vy/sessions/RM_bAqJzJib6c5h)
(31 s), [third](https://cloud.livekit.io/projects/p_53xwsdfy0vy/sessions/RM_x6msGejiQJkx)
(58 s), and [fourth](https://cloud.livekit.io/projects/p_53xwsdfy0vy/sessions/RM_fTLS6urD9gSm)
(7 s). Only the first two had worker dispatch records; the source of the
later two starts is unresolved pending the owner's tap history. The guard
reported `all_owned_closed=false` with one API error and `client_close=ok`;
the later authenticated API check showed zero active rooms/participants.
AppOps showed completed, non-running RECORD_AUDIO operations. The phone
was on its launcher after the stop. September usage displayed 183 → 184
participant minutes and 19 → 23 sessions; rounded minutes are not exact
per-call usage.

The temporary worker launcher now sets process-local `SSL_CERT_FILE` to
the installed certifi CA bundle before SDK imports. The bundle loads 121
CAs locally, and rustls-native-certs documents that variable; actual
LiveKit RTC use of this workaround is **UNTESTED**. This is not an
authorization for another room. Backend, Metro, task-owned ADB and USB
reverse mappings were stopped/removed; port 8082 was untouched.

1. Browser UI: LiveKit billing, usage and four CLOSED sessions inspected.
2. Automated checks: PCM-probe 3/3 offline tests and operator syntax passed;
   backend health HTTP 200 and fresh Metro Android bundle 1,331 modules.
3. Android build: UNTESTED (installed APK reused).
4. Physical device: pre-Start screen, short phone-only sessions, and
   post-stop AppOps observed; speech-driven reply and PCM levels UNTESTED.
