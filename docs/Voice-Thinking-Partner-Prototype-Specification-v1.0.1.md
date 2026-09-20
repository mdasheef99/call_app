Voice Thinking Partner — Prototype Specification v1.0.1

20 September 2026 · Feature scope locked for implementation

This specification narrows the Architecture Charter and Backend Blueprint to the first prototype. It supersedes their broader feature lists for prototype scope, while retaining their authorization, deletion, reliability, and module-boundary rules. No implementation or performance validation is claimed.

1. Goal and audience

Prove that a user can think aloud naturally and return to useful, accurate continuity across calls.

Initial pilot: 5–10 invited adult independent professionals or founders who prepare for and debrief customer meetings. This is a validation audience, not a permanent market restriction. Conversation remains open-ended; meeting preparation is the repeatable test scenario, not a rigid script.

Primary journey: name a project → prepare for a meeting by voice → review recap and saved memory → correct a detail → return after the meeting → continue accurately using the correction.

2. Platform and product defaults

Android-first installable test app; foreground calling on physical Android devices. No iOS or public-store launch in this scope.

Indian English and Hindi-English code switching (Hinglish); automatic conversational switching, without requiring a language toggle.

One private, renameable project per account; no project switching or collaboration.

One AI voice/personality: warm, concise, curious, and willing to challenge assumptions. No relationship or dependency mechanics.

Invite-only authenticated accounts. Use Supabase Auth email sign-in with a one-time code or link and public signup disabled. FastAPI verifies identity and independently enforces account authorization. Phone OTP is deferred.

One active call per account, maximum 15 minutes per call and 30 voice minutes per account per UTC day. These are configurable pilot defaults, not pricing promises.

No web access or external actions in v1. The AI clearly states when current information cannot be verified.

3. Locked features and acceptance criteria

ID

Feature

Required behavior and acceptance

P01

Access and setup

Invited user signs in, sees a brief disclosure that this is AI and text will be retained, grants microphone permission, and names a project. Denied permission shows a recovery action. Uninvited users cannot start calls.

P02

Start/end call

One visible call button. Show connecting, active, reconnecting, and ended/failed states. User can mute or end at any time. Ending stops microphone transmission and playback. Setup failure permits retry without creating duplicate active sessions.

P03

Natural voice

Understand and respond in Indian English/Hinglish. Permit interruption, thinking pauses, and concise answers. Do not rely on a push-to-talk button. Preserve uncertainty when names or numbers are unclear.

P04

Interruption correctness

User speech can stop AI playback. Future responses and recaps do not treat the unheard remainder as communicated. Unknown playback extent is represented conservatively.

P05

Basic recovery

Brief network loss shows reconnecting and attempts recovery for up to 30 seconds. Beyond that, end clearly and offer a new call with available saved context. Never promise uninterrupted recovery; prevent duplicate audio or competing session owners.

P06

Durable history

Persist finalized user utterances and delivered assistant content under the correct account/project. A network failure may lose unconfirmed content; mark an incomplete session rather than inventing missing history.

P07

Short recap

After ending, show processing, ready, or failed-with-retry. Ready recap contains up to 5 key points, explicit decisions, and suggested next steps; omit empty sections. Label suggestions as suggestions, not commitments. Retry must not create duplicate recaps.

P08

Persistent memory

Extract only explicit user-provided project facts, preferences, decisions, and unresolved questions for v1. Every memory links to its source call. Do not promote assistant suggestions or speculative psychological inferences into user facts.

P09

Memory control

Show what was saved. User can edit or delete individual memories. Corrections win over stale extraction jobs and become the source of truth for future calls. No separate approval required for every ordinary memory, but saving behavior is disclosed.

P10

Resume context

Next call retrieves relevant permitted memories and recent recap. It can continue the previous topic without demanding a full restatement. If memory is unavailable, disclose the limitation. Do not force the previous topic if the user starts another.

P11

Delete conversation/data

User can delete a call and its derived recap/memories, or delete all prototype data. Explain dependent deletion before confirmation. Deleted sources cannot be retrieved or recreated by late jobs.

P12

Limits and diagnostics

Enforce concurrent-call and duration limits server-side. Warn one minute before the call cap and end gracefully at the cap. Record usage, latency, and error metadata without putting conversation content into routine logs.

4. Three main screens

Home: project name and rename control, latest recap, recent calls with timestamps, call button, and access to data/account controls. First use provides a short suggestion such as “Talk through a meeting you’re preparing for.” No feed, streaks, or unsolicited reminders.

Call: connection state, elapsed time, mute, and end controls. Show a clear reconnect/error message and time-limit warning. No live transcript editor, camera, screen sharing, or chat composer. Foreground operation only; backgrounding or a phone-call interruption pauses transmission/playback and follows the reconnect/end rule.

Recap and memory: call recap, saved memories with edit/delete controls and source links, and read-only finalized transcript. Distinguish processing from failure. Individual memory deletion leaves the source transcript visible but creates a suppression marker so reprocessing the same source cannot restore it. Deleting the conversation removes its derived outputs as well. Historical recaps are labelled by date; corrected memory is authoritative for future context, and conflicting old recap content must not override it.

Sign-in, first-use disclosure, microphone permission, confirmation dialogs, and account/data settings are supporting screens or sheets; they are not additional product workspaces.

5. Memory rules

Save statements such as “The customer meeting is Thursday” with source date/time and timezone when known. Ask for clarification rather than inventing a calendar date.

Treat “Maybe we should charge ₹499” as an open option, not a final pricing decision.

Link later explicit changes to superseded versions. Preserve the current correction if an older extraction retries.

No inferred health, personality, emotional-dependency, or other sensitive profiling. Do not store passwords or authentication secrets as memories.

Individual memory deletion suppresses re-extraction from the same source. Fresh explicit user input can establish a new memory; do not create a permanent ban on discussing a topic.

If correction/deletion happens during a call, stop stale context delivery and rebuild permitted provider context before continuing. Previously transmitted audio cannot be recalled.

6. Privacy and retention defaults

These are proposed product policies locked for prototype implementation, not claims about any vendor's current policy.

No application-managed raw audio recording. Providers necessarily process live audio; disclose actual provider retention terms before the pilot.

Keep transcripts and recaps for 30 days; expiration removes their derived memories conservatively. A user-edited memory may persist as an independently user-authored source until deletion. Explain this behavior in data controls.

Block newly authorized reads of deleted data immediately after deletion commits; handle in-flight context invalidation explicitly. Target removal from active stores within 24 hours and backups within 30 days. Do not mark deletion complete until tracked cleanup succeeds.

Select provider/storage configurations compatible with the disclosed policy. Any mismatch must be resolved before inviting testers; do not imply erasure of data a provider cannot delete.

Runtime logs contain identifiers, timings, and error codes, not transcripts. Keep diagnostic metadata for 14 days. Internal access to conversation content requires a deliberate support purpose and user consent.

Account isolation and authorization apply to every history, memory, recap, and deletion endpoint. Provider secrets never ship in the app.

7. Prototype architecture subset

Use the modular backend, session coordinator, Postgres source of truth, provider adapters, durable post-call jobs, source provenance, and deletion safeguards already specified. API, realtime agent, and short workers may run separately from one repository.

Implement only the capability interfaces needed for voice, recap, and memory. No research workers, search integration, notification delivery, billing integration, or plugin-loader implementation in v1. Preserve interface boundaries so later additions fit without implementing empty infrastructure for them.

7.1 Stack decision record

Accepted implementation baseline; services have not been configured and performance has not been validated.

Layer

Decision

Qualification

Mobile

React Native + Expo + TypeScript; Expo Router

Android native-audio spike must pass

Engineering builds

Local Expo development builds

Native audio requires a development build, not Expo Go

Pilot delivery

EAS internal-distribution Android APKs

Release-style pilot builds work without a development server

Transport

LiveKit Cloud + React Native SDK

Validate permissions, speaker/Bluetooth routing, interruptions and reconnects

Agent runtime

LiveKit Agents, Python

Pipecat is a fallback for a demonstrated limitation; do not run competing orchestrators

API

Python + FastAPI

Business authorization and application lifecycle rules

Data and identity

Supabase Postgres + Supabase Auth

Private internal schemas; RLS and grants for exposed tables; no privileged key in the app

Database access

SQLAlchemy + psycopg

Bounded connection pools across API, agents and workers

Schema history

Supabase CLI SQL migrations

One authoritative history; do not also introduce Alembic

Post-call jobs

Celery + dedicated Redis broker

Postgres job state, outbox, lease/version checks remain authoritative

Memory retrieval

Scoped structured Postgres retrieval

Defer pgvector until measured retrieval failures justify it

Error monitoring

Sentry

Mobile/backend errors and sampled traces; redact content

Product analytics

PostHog

Explicit activation/return/correction events; session replay off initially

Source and CI

GitHub + GitHub Actions

PR checks, staging smoke tests and on-demand/tagged EAS builds

Voice models

Compare Gemini 3.8 Live and GPT-Live-1

Verify actual account access and exact LiveKit plugin support before testing

Extraction model

Separate structured-output text model

Evaluate factuality, corrections, deletion compatibility and cost

Hosting: Mumbai is the preferred region to investigate for Supabase, the LiveKit agent, and API/worker compute. API/worker hosting vendor and Redis service remain undecided. Check regional availability, connectivity, quotas and cost before provisioning. Agent region, media routing, model processing and telemetry location are separate; this choice does not establish end-to-end Indian data residency.

Provider comparison: use the same scenarios, product instructions, devices and scoring, with documented provider-specific settings. GPT-Live-1 may delegate to a backend reasoning model; compare complete configurations and total session cost, including inference, transport and agent compute. The native-audio comparison does not justify assuming every provider is a drop-in replacement.

CI baseline: on pull requests run TypeScript/lint checks, Python pytest tests, migration application against an isolated database, and authorization/race regression tests. Use one migration runner per deployment. Deploy passing changes to staging and run smoke tests; trigger EAS pilot builds on demand or release tags and upload matching source maps to Sentry. Keep staging/test credentials separate from pilot credentials. Real-device audio tests remain a separate required gate, not a claim that ordinary CI verifies Bluetooth or conversational timing.

Observability: configure Sentry, PostHog, LiveKit telemetry and provider tracing explicitly to exclude transcripts, prompts, memory content and raw audio from routine collection. Postgres owns the usage/cost ledger. PostHog measures product behavior, not authoritative billing. Pin tested dependency/model versions and commit lockfiles.

Revision v1.0.1: records the agreed stack without expanding v1 features. Search remains a v1.1 feature candidate; the document patch version is not a feature release.

8. Verification and pilot gates

The following numerical values are engineering targets for the prototype, not measured results or guaranteed production SLAs. Changes require a recorded specification revision rather than silently weakening a failed test.

Controlled quality suite: at least 20 repeatable call scenarios across two physical Android devices, covering Indian English, Hinglish, pauses, names/numbers, background noise, interruptions, and network loss. Log device/network conditions and sample counts.

At least 19/20 controlled starts connect successfully; p95 call setup within 5 seconds on the nominated stable test network.

Across at least 50 ordinary exchanges, p95 detected-end-of-user-speech to first audible AI response within 2 seconds. Also inspect premature turn endings; fast but interrupting the user is a failure.

Across at least 20 intentional interruptions, p95 user-speech onset to playback stop within 500 ms. No automatic pass based only on server cancellation timestamps.

At least 9/10 short network interruptions recover within the grace period, with no duplicate playback; longer outages end clearly.

Recap and saved memories ready within 60 seconds after a normal call in at least 9/10 controlled cases; remaining cases expose a recoverable status.

All tested account-isolation, deletion-during-extraction, memory-correction, duplicate-finalization, and obsolete-agent races must pass before external pilot access. These are blocking correctness gates.

Ten scripted two-call continuity cases must use the corrected value, exclude deleted memory from retrieval, and avoid treating tentative ideas as decisions. Inspect retrieved context as well as spoken output.

Pilot learning: 5–10 invited testers over two weeks. Observe second-call usefulness, voluntary return, correction frequency, discomfort, task progress, and cost per call. Record whether a return was prompted; do not present assisted testing as organic retention. A small pilot provides directional evidence, not statistical proof of product-market fit.

Spend control: voice-minute limits apply immediately. Before paid trials, set explicit per-account and total currency budgets after measuring provider costs; stop admission when the configured ceiling is reached. No currency amount or permission to incur charges is implied by this specification.

9. Explicitly excluded from v1

Quick web search and background research; reminders and push notifications; calendar/email/bookings; external write actions; multi-project navigation; sharing; uploaded documents; camera/screen sharing; multiple personalities; additional regional languages; offline conversations; background/lock-screen calling; public app-store launch; payments/subscriptions; a plugin marketplace; full event sourcing; knowledge graphs; seamless live provider failover.

Recap action items are text suggestions, not scheduled or executed tasks. Quick search is the first candidate for v1.1 after voice and continuity meet the gates; it is not part of v1 acceptance.

10. Build order and change control

Authenticated app and one project; call start, interruption, end, and history.

Durable post-call recap and explicit memory extraction.

Second-call retrieval, memory correction/deletion, and source suppression.

Reconnect, limit enforcement, operational diagnostics, and failure-race verification.

Run controlled gates, then invite the pilot cohort.

Establish account isolation and source/provenance fields from the first storage implementation; do not defer them until the UI is complete.

A feature enters v1 only if necessary for the primary journey, required to satisfy a correctness gate, or explicitly approved as a scope change. Record the impact on implementation and tests. This specification locks product behavior; vendor selection and measured tuning do not justify expanding the feature list.

Done means: an invited user prepares by voice, reviews and corrects saved context, returns to an accurate debrief, and can delete the data—while the controlled quality and correctness gates pass. A demo that merely connects to a voice model is not sufficient.

Stack references checked during review

LiveKit Expo setup

LiveKit agent regions

Supabase regions

Expo internal distribution

Gemini 3.8 Live

GPT-Live-1 API announcement
