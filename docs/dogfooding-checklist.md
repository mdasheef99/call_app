# Dogfooding checklist — does this feel natural?

Use real topics you want to think through, such as preparing for or debriefing a meeting. Record what happened without adjusting your speech to help the app. Repeat a few scenarios deliberately after a change so results can be compared. This sheet captures observations; the [prototype specification](Voice-Thinking-Partner-Prototype-Specification-v1.0.1.md) §§3, 8, and 10 remains the acceptance and pilot-readiness authority. Check [HANDOFF.md](HANDOFF.md) for the current implementation and device evidence.

Mark each case **pass**, **partial**, **fail**, or **not available**. A pass means the described behavior was actually observed on a physical device. A mocked test, successful connection, or generated response alone does not prove audible AI speech or delivered content. Keep subjective impressions alongside results; do not turn them into a new release threshold.

## Stage A — voice diagnostic, during an approved live AI-audio trial

The current development screen is a diagnostic, separate from the Home screen's simulated product call. Start this stage only when the voice worker and provider trial have been separately authorized under the current account limits and budget. It cannot test recap, durable history, or memory. The cases below explore the voice behavior in specification P02–P04; they do not establish full P02–P04 acceptance.

| ID | Try during a real conversation | Record the observable result |
| --- | --- | --- |
| V1 | Finish a thought normally. | Did audible AI speech start promptly, without cutting you off? Note measured timing if available; otherwise label it an estimate. |
| V2 | Pause mid-sentence to think, then continue. | Did the AI wait for the continuation? Note the pause length. |
| V3 | Use natural acknowledgements such as “haan,” “acha,” or “hmm.” | Did the AI understand whether you were continuing or handing over the turn? |
| V4 | Switch between Indian English and Hinglish, including within a sentence. | Did it understand and respond appropriately without making you switch to unnatural speech? |
| V5 | Mention a real name, number, or acronym. | Did it get the detail right or acknowledge uncertainty instead of guessing? |
| V6 | Interrupt while the AI is audibly speaking. | Did playback stop? Note the audible stop time if measured. Ask a follow-up that could reveal whether it assumes the unheard remainder was delivered. |
| V7 | Interrupt, then stay quiet briefly. | Did it avoid automatically replaying the interrupted remainder or treating it as already heard? |
| V8 | Have a quick exchange and a longer, approved call. | Did turn-taking degrade as the call continued? Note duration and any waits that felt like a freeze. |
| V9 | Try an approved call on Wi-Fi and, separately, mobile data or moderate background noise. | Record network/noise conditions and failures; do not combine different conditions into one pass. |
| V10 | Mute and End. | Did speech transmission and playback stop as expected? Record any remaining microphone indication or cleanup error. |

After each call, ask: Did I slow down, avoid pauses, or switch to “clean English” for the app? Did a follow-up question help me think? Did the AI challenge an assumption usefully? Would I choose to use it for a real topic tomorrow? These are candid notes, not pass/fail gates.

The current diagnostic does not expose a finalized transcript. Judge understanding from what the AI audibly says; inspect stored text only when that product feature exists. Manual timing impressions do not satisfy the measured latency and interruption gates in specification §8.

## Stage B — full product journey, as each feature becomes available

Use the same real meeting-preparation and return scenario from specification §1. Mark a case **not available** until its actual product behavior exists. These checks supplement the repeatable correctness tests required by specification §§3 and 8.

| ID | Try across calls and data controls | Record the observable result |
| --- | --- | --- |
| D1 | Sign in as an invited user, read the disclosure, grant or deny microphone permission, and name the project. | Was access limited to the invited account? Did denial provide a recovery action? (P01) |
| D2 | End a substantive call, then inspect finalized history. Interrupt one AI response during the call. | Are your finalized utterances and only delivered assistant content represented honestly? Is an incomplete session identified instead of filled in? (P04, P06) |
| D3 | Inspect the recap, including a tentative idea and a firm decision. | Are key points grounded in the call, decisions explicit, and suggested next steps clearly labelled as suggestions? Is processing or failure visible when applicable? (P07) |
| D4 | State an explicit project fact and a tentative option. Inspect saved memories and their source calls. | Is the fact saved accurately with provenance, while the option remains tentative? Are unsupported inferences absent? (P08) |
| D5 | Correct a saved detail, then return in a later call. | Does the correction remain authoritative in retrieval and speech, even if old material is reprocessed? (P09–P10) |
| D6 | Delete one memory, then a call or all prototype data using the available controls. | Is the dependent deletion explained and confirmed? Does deleted material stay out of later retrieval and reprocessing? (P09, P11) |
| D7 | Return to the same topic, then start a different topic on another call. | Does relevant permitted context help without forcing the old topic into an unrelated discussion? Is missing memory disclosed? (P10) |
| D8 | When implemented, exercise network loss, reconnection, mute/End, and call limits. | Are state, audio, retry, warning, and stop behavior clear? Record any duplicate playback or competing session. (P02, P05, P12) |

## Formal pilot gate — separate from this sheet

Use specification §8 for controlled device, latency, interruption, recovery, continuity, isolation, deletion, race, and spend checks, and §10 for build order. Real unscripted calls reveal usability; repeatable cases establish whether a fix holds. The pilot follows those gates. A count of dogfood calls, several good days, a 2–3 week time box, or a strong desire to return does not replace them. If progress stalls after a few weeks, review the failures and the current gates before deciding the next experiment.

## Per-call log

Copy this block for each session. Avoid putting raw conversation content, credentials, or sensitive personal details in routine issue logs; use a short scenario description and the minimum excerpt needed to reproduce a defect. Any content-bearing test artifact follows the prototype's privacy and retention rules (specification §6).

```text
Date/time and timezone:
Code revision / app build / model version:
Device / Android version:
Network and noise conditions:
Call duration:
Real topic or repeatable scenario ID:
Language mix:
Case IDs attempted, each with pass / partial / fail / not available:
What I observed (including audible behavior and any timing method):
What I expected:
Reproduction steps or relevant call/session ID:
Did I change how I spoke for the app? How?
Would I choose to use it for a real topic tomorrow? yes / no / unsure
Biggest break in naturalness:
Follow-up issue or test to add:
```
