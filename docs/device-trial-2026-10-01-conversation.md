# Device trial — first speech-driven conversation, 2026-10-01

Owner requested the reviewed corrected worker and one phone test. The named
worker ran with hot reload disabled, the process-local CA bundle, and the
per-connection PCM audio-field/rate correction. A separate room cutoff was
60 seconds from the guard's first room observation; the idle worker stays
running until the owner requests stop (or the guard fails).

Content-free worker evidence (Asia/Calcutta timestamps):
- One dispatch at 03:51:04.796; session started at 03:51:14.495.
- Google connection opened at 03:51:15.594.
- Input-transcription events appeared, without storing their text here.
- Seven completed provider turns; 108 returned audio chunks / 1,388,174 bytes.
- Final submitted counters: 1,134 chunks / 1,814,400 bytes.
- Room deletion logged at 03:52:10.787, followed by disconnect/cleanup.
- Receive APIError code 1000 followed deletion; it is not evidence that
  the preceding working conversation failed at Google.

Owner reported hearing replies and chatting with the AI. This establishes
the first owner-observed speech-driven conversation on the LG Wing.
Owner also reported Mute worked, then Unmute produced an error and returned
to the test/permission page. Exact error and timing are not established.
The room cutoff may explain an Unmute near shutdown; do not assert an
independent microphone-toggle defect without evidence. No retry authorized.

Browser UI: UNTESTED. Automated suite: not rerun for this trial.
Android build: UNTESTED (existing installed development client used).
Physical device: owner-observed conversation and Mute/Unmute behavior above.
Authenticated post-call listing: zero active rooms and zero participants.
OS microphone indicator confirmation remains pending from the owner.
No usage refresh performed, per the owner's instruction.
