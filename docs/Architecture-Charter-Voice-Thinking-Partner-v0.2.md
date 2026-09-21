Architecture Charter — Voice Thinking Partner

Version 0.2 · 20 September 2026 · Proposed implementation baseline

Purpose

Build an India-native voice thinking partner that supports natural conversation, useful continuity, and background capabilities. Optimize first for conversational quality, correctness, recoverability, and ease of change. This charter defines constraints; it is not a claim that the architecture has been implemented or validated.

1. Structure and ownership

Start with one codebase: a modular monolith with separately runnable API, realtime-agent, and worker processes. Use Postgres as the durable source of truth. Keep media transport separate from ordinary API traffic. Split services only for demonstrated isolation, scaling, or team needs.

Boundary

Owns and guarantees

Identity and access

User identity, membership, authorization, and consent

Conversations

Session lifecycle, ordered conversation events, finalized history

Realtime runtime

Provider connection, turn coordination, playback state, context delivery

Memory and projects

Project scope, retained knowledge, provenance, correction, deletion

Capabilities and jobs

Tool validation, durable work requests, execution state, cancellation

Artifacts

Reports, summaries, versions, and access-controlled retrieval

Usage

Entitlements, budget reservations, consumption, reconciliation

Modules expose explicit interfaces and own their writes. Cross-module access uses those interfaces or deliberately defined read models. Shared infrastructure must not become shared business logic. External provider SDKs stay inside adapters.

2. Domain and interface contracts

Use distinct objects for Session, Event, Job, Memory, Artifact, and Project. An event records a fact; it does not replace every object's current state. Keep an append-oriented event log alongside ordinary state tables; full event sourcing is not required.

Public and persisted contracts include stable identifiers, schema versions, explicit errors, and ownership scope. Events have per-session ordering and correlation identifiers. Define permitted state transitions and enforce them transactionally. Distinguish commands requesting action from events reporting completed facts.

Start with registered capability modules. Each declares input/output schemas, permissions, side effects, execution mode, deadline, cancellation, and retry semantics. Provider adapters expose supported capabilities and reject unsupported behavior explicitly. Dynamic plugin loading is deferred.

3. Non-negotiable guarantees

Server code derives identity and checks authorization for every operation; model output never grants permission.

Every durable job request is committed before the app claims acceptance. Only committed outcomes may be reported as completed.

Retries cannot duplicate business outputs or usage charges. External side effects use provider idempotency where available; ambiguous outcomes require reconciliation before retry.

Memories distinguish explicit statements from inferences, retain sources, and support supersession. Retrieval is restricted to authorized scope before semantic ranking.

Deletion revokes retrieval access immediately and prevents in-flight jobs from recreating deleted content. Physical deletion follows an explicit retention policy covering derived data, files, and backups.

Conversation history distinguishes generated text from delivered speech; interruptions must not imply that unheard content was communicated.

4. Realtime and background work

Audio processing never blocks on research, extraction, or report generation. Quick tools use asynchronous handlers with deadlines; long work uses durable jobs. Separate their resource pools. Bounded queues, concurrency limits, and admission control protect active calls.

Load a bounded context snapshot at session start. Retrieve additional context when relevant and track delivered context versions. One session coordinator owns interruption handling and decides when background results enter the conversation. Results carry user, project, job, and originating-session identifiers; stale results never enter a different session automatically.

Choose either native realtime audio or a cascaded STT–LLM–TTS configuration for the initial prototype. Benchmark Indian English, Hinglish, noise, interruptions, latency, and cost before choosing providers.

5. Reliability and failure behavior

Use a transactional outbox for essential database-to-queue handoffs, idempotent consumers, bounded retries with backoff, and recoverable job state. Redis Pub/Sub may announce disposable updates; it is not the durable work ledger. A reconciliation process detects stranded work and reservations.

Scenario

Required behavior

Search or memory unavailable

Continue where useful, clearly state the limitation, never fabricate a result

Authorization unavailable

Deny the protected operation

Research completes after disconnection

Save its artifact; use permitted notification or later retrieval

Worker crashes after saving output

Retry resolves to the existing output

Call disconnects

Apply a defined reconnect grace period; expire abandoned session ownership

User cancels a job

Persist cancellation, stop further work where possible, suppress obsolete delivery

Voice provider fails

Report disruption and offer reconnection; seamless failover is not assumed

Ending a call does not implicitly cancel explicitly requested background research. Cancellation cannot promise to undo an already completed external action.

6. Quality, cost, and evolution

Trace sessions, tools, jobs, and artifacts with correlated identifiers. Measure latency distributions, interruption stop time, reconnect success, job failures, memory errors, and cost per session. Keep raw audio and transcript content out of routine logs; recording is off by default unless deliberately enabled with an explicit purpose and retention policy.

Before pilot release, set measurable latency and cost budgets from device/network trials. Test interruption history, contradictory memories, cross-user isolation, duplicate execution, deletion during extraction, and late results. Version models, prompts, and retrieval configuration; compare changes against a fixed evaluation set.

Use backward-compatible database and message migrations, rollback plans, and tested backup restoration. Record significant decisions with their rationale and a concrete revisit trigger. Defer microservices, a plugin marketplace, full event sourcing, and a knowledge graph until evidence warrants them.

Implementation baseline and remaining evidence

Prototype Specification v1.0.1 section 7.1 is the stack decision record. Baseline: React Native/Expo/TypeScript and Expo Router; LiveKit Cloud with LiveKit Agents Python; FastAPI; Supabase Postgres/Auth; SQLAlchemy/psycopg; Supabase CLI SQL migrations; Celery/Redis; Sentry; PostHog; GitHub Actions; local development builds plus EAS internal distribution. Pipecat is a fallback, not a second orchestrator. Structured memory retrieval comes first; pgvector is deferred.

Voice-provider choice, Android media behavior, exact SDK/plugin compatibility, post-call model, hosting vendor and regional placement still require evidence. Mumbai is a preferred candidate, not a residency guarantee. Prototype performance targets and retention defaults are defined in the specification; they remain to be validated against actual providers and deployment capabilities. Use one migration history and preserve Postgres-authoritative job state and transactional race safeguards.

The broader capability architecture supports future research and tools; the prototype specification determines what is actually built in v1. This revision records stack alignment, not expanded scope or implemented infrastructure.

Design references

Based on the supplied architecture summary and our product/backend discussion. Supporting references previously reviewed:

Microservice trade-offs

Transactional outbox pattern

Control and limit retries

Redis Pub/Sub delivery semantics
