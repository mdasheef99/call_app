Backend Implementation Blueprint and Architecture Stress Test

Version 0.2 · 20 September 2026 · Proposed design, not a deployed implementation

Basis: Architecture Charter v0.2 and the product/backend discussions in this conversation. This document makes implementation choices explicit without claiming provider performance or runtime correctness. The stress test is a tabletop review of failure sequences; executable integration, load, and device tests remain required.

1. Scope and concrete defaults

This blueprint describes the broader backend, including future research. Prototype Specification v1.0.1 controls release scope: build voice, recap, correctable memory and reconnect first. Research flows, research workers, report object storage and notification delivery are deferred; their designs below are retained for future implementation.

Implementation baseline: Python/FastAPI, Supabase Postgres and Auth, SQLAlchemy with psycopg, Supabase CLI SQL migrations, Celery workers with a dedicated Redis broker, and LiveKit Cloud transport. Start with structured retrieval; pgvector and its embedding table are deferred until justified. Run API, realtime agents, and workers independently from one repository. Keep cache/rate-limit Redis separate from the durable broker's eviction and resource policies. Celery delivery is a trigger; Postgres jobs remain authoritative.

Use one native-audio provider initially, behind a capability-aware adapter. Benchmark it before committing; Sarvam STT/TTS belongs to an alternative cascaded configuration, not automatically around native audio. LiveKit Agents Python is the baseline orchestrator. Pipecat is a fallback only for a demonstrated limitation. Exactly one coordinator owns turn and interruption decisions.

MVP assumptions: personal accounts, private projects, one active call per account, read-only search/research, no email sending or bookings. Sharing and irreversible external actions require additional permission and reconciliation designs. Audio recording is disabled by default. Project-independent conversations use the user's default project, avoiding nullable scope in deduplication keys.

2. Deployment and dependency boundaries

flowchart TD
    App["Mobile app"] --> API["Control API"]
    App <-->|Audio| Transport["Managed media transport"]
    Transport <--> RT["Realtime agent and coordinator"]
    RT <--> Provider["Voice provider adapter"]
    API --> Modules["Domain module interfaces"]
    RT --> Modules
    Modules --> DB["Postgres and outbox"]
    DB --> Dispatch["Dispatcher and reconciler"]
    Dispatch --> Queue["Job broker"]
    Queue --> Workers["Short and research workers"]
    Workers --> Modules
    Workers --> Objects["Private object storage"]

This is deployment topology, not permission to bypass module ownership. A worker invokes module services; only the owning repository accesses a module's tables. An application service may compose multiple module operations in one shared Postgres unit of work. This preserves atomicity without distributing transactions across services. Network/model calls never occur inside a database transaction.

Proposed code location

Responsibility

app/api/

Authentication middleware, HTTP routes, control-event stream

app/modules/identity/

Principal resolution and account access

app/modules/conversations/

Session state, events, utterances, ownership leases

app/modules/knowledge/

Projects, memories, provenance, deletion scopes

app/modules/jobs/

Capability contracts, jobs, attempts, cancellation

app/modules/artifacts/

Reports, versions, source links, access

app/modules/usage/

Budget reservations and reconciled ledger

app/runtime/

Turn coordination, playback bookkeeping, context assembly

app/adapters/

Provider, transport, embedding, search, push integrations

app/workers/

Task entry points calling module interfaces

app/infrastructure/

Database unit of work, outbox, broker, telemetry

supabase/migrations/, tests/

Sole SQL migration history and contract/integration/device checks

No domain module imports a provider SDK. No worker constructs another module's SQL. Dependency tests reject these imports. The database owner/migration role is separate from runtime credentials.

3. Interface contracts

Signatures below are language-neutral contracts, not executable code. Principal is authenticated server context, never a trusted body parameter. Scope contains account and project IDs. Revision is an integer used for optimistic concurrency. All identifiers are UUIDs except opaque provider references. Timestamps use UTC database time.

Owner and operation

Inputs

Return and guarantee

Conversations start_session

principal, project_id, request_key

session_id, state, revision; repeated key returns same session

Conversations claim_session

internal actor, session_id, expected_epoch

lease(owner_id, epoch, expires_at); only one current owner

Conversations resume_session

principal, session_id, last_event_seq

session snapshot, missing events, new credentials if allowed

Conversations append_event

lease, source_key, type, payload

event_id, seq; rejects obsolete epoch and deduplicates source_key

Conversations close_session

principal/internal actor, session_id, expected_revision

closing/closed snapshot; queues finalization once

Runtime interrupt

session_id, response_id, playback_cursor

stops playback, requests provider cancellation, records delivered extent

Knowledge retrieve

principal, scope, query, token_budget

authorized memories with versions, sources, deletion epochs

Knowledge correct_memory

principal, memory_id, expected_revision, text, request_key

new version; old version superseded atomically

Knowledge forget_source

principal, source_scope, request_key

deletion_id, blocked_at, purge_state; prevents future retrieval

Jobs submit

principal, scope, capability, arguments, request_key

job_id, state; persisted acceptance and budget reservation

Jobs claim

internal actor, job_id

attempt_id, lease_epoch, deadline; only eligible jobs

Jobs cancel

principal, job_id, expected_revision

current terminal state or cancel_requested

Jobs complete

attempt lease, output manifest, source_epochs

artifact_id or rejected outcome; validates lease, cancellation, deletion

Artifacts get

principal, artifact_id

current authorized content through an authorization-checking download endpoint

Usage reserve

principal, operation_id, maximum_cost

reservation or budget_exceeded; serializes competing reservations

Usage record

operation_id, attempt_id, provider_usage_key, usage

deduplicated ledger entry; captures actual retry consumption

Errors are structured: not_found, conflict, stale_lease, cancelled, source_deleted, budget_exceeded, rate_limited, temporarily_unavailable, unsupported_capability. Cross-account references return not_found without disclosing existence. Non-idempotent calls never retry automatically. Reusing a request key with a different canonical argument hash returns conflict.

Capability declarations include schema_version, input/output schemas, required permissions, side_effect_class, execution_mode, timeout, retry_policy, cancellation_policy, and budget class. Search results and retrieved documents are untrusted data, not authority to execute tools or change instructions.

Provider interfaces expose connect, receive events, update context, cancel response, close, and declared features. The adapter translates provider events into domain events; it does not own durable session state. Unsupported context truncation requires restarting provider context from the delivered history rather than pretending truncation succeeded.

External control API

POST /v1/sessions, GET /v1/sessions/{id}, POST /v1/sessions/{id}/resume, POST /v1/sessions/{id}/close; POST /v1/jobs, GET /v1/jobs/{id}, POST /v1/jobs/{id}/cancel; GET /v1/artifacts/{id}; PATCH /v1/memories/{id}; POST /v1/deletions.

Mutations use Idempotency-Key; revision-sensitive edits use If-Match. Job creation returns HTTP 202 only after commit. Control updates use a resumable event stream with event cursors; polling remains a recovery path. Audio does not traverse these JSON endpoints. Issued media credentials are short-lived and scoped to the session. Artifact downloads recheck authorization and source validity at request time; direct signed object URLs would create a revocation window and are not the default. Bytes already downloaded cannot be recalled.

4. Database schema specification

This is a logical schema for migration authors, not executed DDL. Every scoped table carries account_id; dependent references use composite (account_id, id) foreign keys to prevent cross-account attachment. IDs are UUIDs; states are constrained text; timestamps are timestamptz; revisions/epochs/sequences are bigint. JSONB is reserved for versioned event payloads and capability arguments, not core lifecycle fields.

Table / owner

Principal columns

Constraints and indexes

accounts / identity

id, auth_subject, status, deletion_epoch

unique auth_subject

projects / knowledge

id, account_id, name, is_default, deleted_at, deletion_epoch

unique(account_id,id); one live default per account

sessions / conversations

id, account_id, project_id, state, revision, owner_id, owner_epoch, lease_until, reconnect_until, next_seq, provider_ref, request_key

unique(account_id,request_key); partial unique account_id over nonterminal states

conversation_events / conversations

id, account_id, session_id, seq, source_key, type, schema_version, occurred_at, received_at, payload, redacted_at

unique(session_id,seq), unique(session_id,source_key); index(session_id,seq)

utterances / conversations

id, account_id, session_id, speaker, response_id, generated_text, delivered_text, delivered_audio_ms, delivery_status

unique(session_id,response_id) where response_id present; delivery_status distinguishes confirmed/estimated/unknown

source_scopes / knowledge

id, account_id, kind, resource_id, epoch, deleted_at

unique(account_id,kind,resource_id); locks coordinate deletion and derived writes

memory_items / knowledge

id, account_id, project_id, current_version_id, revision, deleted_at

index(account_id,project_id,deleted_at)

memory_versions / knowledge

id, account_id, item_id, version, text, assertion_kind, status, supersedes_id, extractor_version, created_at

unique(item_id,version); assertion_kind explicit/inferred; status active/superseded/blocked

memory_sources / knowledge

account_id, version_id, source_scope_id, observed_epoch, event_id

composite PK(version_id,source_scope_id,event_id); reverse index(source_scope_id)

memory_embeddings / knowledge

account_id, version_id, embedding_model, vector, created_at

unique(version_id,embedding_model); dimension fixed per model migration

jobs / jobs

id, account_id, project_id, origin_session_id, capability, args, args_hash, state, revision, request_key, attempt_epoch, lease_until, deadline, available_at, cancel_requested_at, result_id

unique(account_id,capability,request_key); index(state,available_at)

job_attempts / jobs

id, account_id, job_id, epoch, worker_id, state, started_at, finished_at, provider_ref, error_code

unique(job_id,epoch)

job_sources / jobs

account_id, job_id, source_scope_id, observed_epoch

PK(job_id,source_scope_id); references every input source and relevant scope

artifacts / artifacts

id, account_id, project_id, job_id, output_slot, state, current_version, deleted_at

unique(job_id,output_slot); state staged/ready/blocked

artifact_versions / artifacts

account_id, artifact_id, version, object_key, checksum, byte_count, source_manifest

PK(artifact_id,version); immutable private object keys

artifact_sources / artifacts

account_id, artifact_id, source_scope_id, observed_epoch

PK(artifact_id,source_scope_id); reverse index for deletion

outbox / infrastructure

id, account_id, aggregate_id, type, schema_version, payload_ref, available_at, lease_until, published_at, attempts

index unpublished available_at; messages contain IDs rather than transcript copies

deliveries / jobs

id, account_id, job_id, artifact_id, channel, destination_id, state, attempt_count, acknowledged_at

unique(job_id,channel,destination_id); destination_id non-null

usage_reservations / usage

id, account_id, operation_id, ceiling_microunits, held_microunits, state, expires_at

unique(account_id,operation_id); nonnegative amounts

usage_ledger / usage

id, account_id, operation_id, attempt_id, provider_usage_key, amount_microunits, kind

unique(account_id,provider_usage_key); adjustments are new entries

deletion_requests / knowledge

id, account_id, request_key, target_scope_id, state, blocked_at, completed_at, error_code

unique(account_id,request_key); state blocked/purging/completed/failed

Use non-null deduplication keys; nullable unique columns otherwise allow repeated nulls. Cross-row invariants belong in transactions and constraints, not CHECK expressions querying other rows. If introduced, pgvector retrieval always includes account/project authorization and active-source predicates; vector similarity is ranking, not authorization. Start with scoped exact retrieval if small; benchmark approximate indexing for recall and filtering before adopting it.

5. Transactions and race resolution

Lock order: account access/budget row, source scopes sorted by ID, session or job, memory/artifact rows. Keep transactions short. All competing operations follow the same order; retry bounded deadlocks at the transaction boundary.

Accept job: authorize; lock account budget and source scopes; validate source epochs; reserve budget; insert job + job_sources + outbox; commit; return accepted. Duplicate request key returns the existing job, without another reservation.

Claim/heartbeat: atomic compare-and-set on eligible state and expired lease; increment attempt epoch. Every worker commit includes this epoch and checks lease validity. A lease expiring alone does not stop an old process; fencing rejects its writes after a replacement claim. External provider calls can still incur cost, so they require bounded deadlines and reconciliation.

Complete research: upload to a private immutable staging key before the transaction; then lock relevant scopes and job; reject changed epochs, invalid lease, cancellation, or terminal state. Through module interfaces in the shared transaction, create the artifact/version, mark job succeeded, settle known usage, and append delivery outbox. A crash before commit leaves an orphan staged object for cleanup; a crash after commit retries to the existing artifact. Cleanup only deletes old unreferenced staging objects after a grace period.

Cancel vs complete: both serialize on the job row. If completion commits first, cancel returns succeeded; it does not claim to undo completion. If cancellation commits first, completion is rejected. Running work moves to cancel_requested until stopped or reconciled. Recheck cancellation immediately before any external side effect.

Delete vs extraction: deletion locks source scope, increments epoch, and tombstones it. Reads authorized after the tombstone commit exclude that source and its dependents using source validity, even before physical cleanup. In-flight retrievals recheck epochs before context injection; already transmitted data cannot be recalled. Extraction commits lock the same scope and compare captured epoch; stale outputs are rejected. Correcting a memory increments its revision; extraction from older snapshots cannot overwrite the user's correction. Conflicting later inferences remain separate candidates.

Outbox/broker: claim outbox rows briefly, publish outside the DB transaction, and mark publication. Crash after publish permits duplicates. A reconciler republishes jobs still queued without a live attempt and recovers expired attempts according to retry policy. Thus an acknowledged broker publication followed by broker data loss does not permanently strand work. Retry count and deadline bound repeated failures.

6. State machines

Session lifecycle

stateDiagram-v2
    [*] --> starting
    starting --> active: Media and provider ready
    starting --> failed: Setup deadline exceeded
    active --> reconnecting: Connection lost
    reconnecting --> active: Resume within grace
    active --> closing: End requested
    reconnecting --> closing: Grace expired or end requested
    closing --> closed: Finalization scheduled
    failed --> [*]
    closed --> [*]

Lifecycle and conversational activity are separate: listening/thinking/speaking describe activity while the session remains active. Provider errors enter a bounded reconnect path or close with a reason. An idempotent watchdog closes abandoned starting/closing sessions. Terminal sessions never reopen; a later call is a new session linked to the project. Late usage can settle after close without reopening it.

Job lifecycle

stateDiagram-v2
    [*] --> queued
    queued --> running: Lease acquired
    queued --> cancelled: Cancel before claim
    running --> retry_wait: Retryable failure
    retry_wait --> queued: Backoff elapsed
    running --> succeeded: Atomic result commit
    running --> failed: Permanent error or deadline
    running --> cancel_requested: Cancellation accepted
    cancel_requested --> cancelled: Stopped or lease reconciled
    retry_wait --> cancelled: Cancel accepted
    queued --> failed: Deadline expired
    retry_wait --> failed: Deadline expired
    succeeded --> [*]
    failed --> [*]
    cancelled --> [*]

Expired running leases move to retry_wait or failed under reconciliation. A cancelled external side effect may require a separate reconciliation record rather than a false guarantee of undo; MVP capabilities are read-only. Job success is terminal even when notification delivery fails. Delivery state is tracked independently.

7. End-to-end flows

A. Call, interruption, reconnect

API authenticates, reserves a bounded voice budget, and creates a starting session. A partial uniqueness constraint rejects a second live call.

Agent claims an epoch lease, receives scoped credentials, loads authorized bounded context, and marks active only when connections are ready.

Provider events are normalized; finalized utterances and meaningful state changes are persisted asynchronously with bounded buffering. Partial audio/transcripts are not all stored as durable events.

On interruption, stop client playback promptly and request provider cancellation. Record the last confirmed playback cursor; mark uncertain delivery honestly. Update provider context to exclude unheard output or restart its context if required.

On network loss, mark reconnecting. Resume authenticates the same account and obtains events after the client's cursor. If another agent takes over, increment ownership epoch, revoke old media access where supported, and reject old epoch callbacks. The client ignores frames/control messages tagged with obsolete generation IDs.

End or expired grace closes the session and queues one finalization job. Ongoing explicitly requested research survives call closure.

Deletion in active context: tombstoning cannot make a provider forget audio already processed. On a relevant deletion, invalidate the session context and stop output; rebuild a fresh provider session with permitted history before resuming. Revocation uses push plus periodic epoch checks with a bounded freshness lease. Do not claim instantaneous erasure across offline processes or third-party retention.

B. Research during a call, delivery after it

Tool handler validates scope/arguments and atomically submits a job. The AI acknowledges only persisted acceptance.

Worker claims a lease, fetches permitted context, and performs bounded research. Checkpoints store source references, progress, and model/prompt versions; they are recoverable hints, not authority to bypass cancellation/deletion checks.

Report storage and success commit follow section 5. Failed delivery cannot roll back a completed report.

Coordinator rechecks current session, topic, scope, cancellation, and source validity before presenting a result at a safe speaking boundary. A mismatched topic leaves the result available in the UI instead of interrupting.

If disconnected, persist delivery intent and optionally send a content-minimal push. App polling retrieves the report even if push fails. On a later call, explicitly retrieve relevant finished work; do not replay an old live-context command.

C. Memory, correction, deletion

Finalization consumes only finalized history and delivered assistant content, with source epochs captured. The extraction model proposes explicit/inferred memories with evidence links.

Knowledge service validates proposals, checks sources, stores versions, and makes them available through structured retrieval. If embeddings are later introduced, extraction schedules them separately; embedding failure must not lose memories.

User correction uses expected revision. Two simultaneous edits yield one success and one conflict, not silent overwrite.

Deletion blocks the source immediately for new retrieval. Derived memory/artifact links make dependent content discoverable for cleanup; conservatively block mixed-source outputs until regenerated without the removed source.

Purge removes text, embeddings, object versions and caches according to policy; provider deletion requests are tracked where supported. Backups have a defined expiry, and restoration reapplies tombstones before serving traffic. Minimal deletion metadata excludes original sensitive content.

8. Architecture stress-test results

Method: manually follow failure interleavings against the charter, then revise the blueprint to close logical gaps. No server, database, provider, or device test was executed. “Addressed” means a specified mitigation exists, not that production correctness is proven.

Priority: P0 threatens isolation, deletion, or duplicate side effects; P1 threatens core continuity, reliability, or cost; P2 affects operational quality.

ID / priority

Adversarial sequence and original gap

Design response incorporated

Required executable check / residual risk

S01 P1

User interrupts after provider generates a whole answer but before playback finishes

Delivered cursor separate from generated text; cancel/truncate or rebuild context

Play half a response, interrupt; subsequent answer must not assume unheard steps. Device timing remains unmeasured

S02 P0

Agent A pauses; lease expires; B resumes; A wakes and writes/speaks

Epoch fencing on writes, client generation checks, transport revocation

Race two agents; stale writes rejected and old media suppressed. Transport-specific fencing must be proven

S03 P1

HTTP response lost after job acceptance; client retries

Scoped request key + args hash + unique constraint

Repeat submission concurrently; exactly one job and reservation

S04 P1

DB commits job; process crashes before queue publish

Transactional outbox

Kill after commit; dispatcher eventually triggers job

S05 P1

Publish succeeds; dispatcher crashes before marking sent

Duplicate-tolerant claim and result commit

Deliver identical message twice; one committed artifact

S06 P1

Broker acknowledges then loses queued messages

DB reconciler republishes eligible stranded jobs

Clear broker after publication; DB-backed work recovers within configured recovery interval

S07 P0

Worker uploads output then crashes before/after DB commit

Staged immutable keys, atomic artifact/job/outbox commit, orphan collection

Kill on both sides of commit; one visible artifact, no broken pointer, stale objects cleaned

S08 P0

Cancellation and completion arrive together

Shared row lock; first committed transition wins

Execute both orders; terminal state and UI remain consistent

S09 P0

User deletes transcript while extraction/model call runs

Scope tombstone + epoch lock/recheck at commit

Pause extraction, delete, resume; zero resurrected memories or embeddings

S10 P0

Deleted memory already loaded into a live provider session

Context invalidation, stop/rebuild, bounded freshness lease

Delete while speaking; stop stale context delivery and measure propagation window. Already transmitted audio cannot be recalled

S11 P0

User corrects memory while older extraction retries

Version CAS + provenance; no blind upsert over explicit correction

Run stale write after correction; correction remains current

S12 P0

Model/tool supplies another account's project/artifact ID

Server principal, composite scope FKs, scoped retrieval

Fuzz foreign IDs across all entry points; no content or existence leakage

S13 P1

Research finishes after call ends or changes topic

Durable report, separate delivery state, coordinator relevance check

End call/change topic before result; no stale audio injection; report remains retrievable

S14 P1

Push sent but acknowledgement lost; retry sends twice

Stable delivery key, client deduplication, content-minimal notification

Duplicate pushes yield one in-app item. Exactly-once push appearance is not promised

S15 P1

Research saturation consumes all model/DB connections

Separate pools, bounded concurrency, account budgets and admission control

Saturate research; measure voice tail latency and DB pool contention

S16 P1

DB fails while provider keeps generating and billing

Bounded event buffer and ownership/budget freshness lease; stop when exhausted

Disconnect DB; no unlimited unrecorded call or spending; recovery does not invent lost history

S17 P1

Provider response times out but request incurred cost

Attempt-level usage ledger and reconciliation; bounded retries

Simulate ambiguous timeout; genuine repeated inference cost recorded once per attempt, not hidden

S18 P0

Old backup restores deleted text

Tombstone journal recovery before serving; blocked startup until reconciliation

Restore snapshot preceding deletion; deleted sources remain inaccessible

S19 P1

Old worker receives new event schema after deploy

Versioned contracts, compatible readers, quarantined unknown schemas

Mixed-version deployment; no silent payload misinterpretation

S20 P0

Web source includes instructions to exfiltrate memory

Treat source as data, tool allowlist, server permissions, minimal outbound context

Malicious page cannot authorize new tool calls or leak unrelated context

S21 P1

Embeddings are unavailable or model dimension changes

Memory authoritative without vectors; model-versioned embedding migration

Retrieval degrades explicitly; no mixed-dimension index writes

S22 P1

Outbox/reconciliation repeatedly retries permanent errors

Typed errors, bounded deadline/attempt budget, failed-work inspection

Permanent errors terminate; no retry storm or endless reservation

Four traced races

Reconnect: A owns epoch 7 → lease expires → B atomically claims epoch 8 → A sends append(epoch 7) → stale_lease; client accepts only current generation. Database fencing alone does not stop audio, hence the explicit transport/client rule.

Delete: worker reads source epoch 3 → deletion locks source, changes epoch to 4 and commits → worker locks source and tries completion with epoch 3 → source_deleted. If completion wins first, deletion subsequently blocks its newly committed output through provenance.

Cancel: completion and cancellation lock the same job. Completion first yields succeeded and cancellation reports that state. Cancellation first yields cancel_requested and completion cannot publish a success artifact. No timestamp guessing determines the winner.

Duplicate completion: first worker commits artifact (job J, slot report) and terminal job state → retry sees succeeded and returns existing artifact → uniqueness is a final backstop. Additional provider calls may still cost money; business idempotency is not free inference.

9. Implementation slices and acceptance gates

These are architecture work packages, not claims of completed code. For v1 execute slices 1–3, the memory portions of 5, and applicable operations in 6. Defer research slice 4 and its storage/delivery machinery. Slice 5 does not depend on research. The prototype specification controls the release build order.

Slice

Create/implement

Acceptance evidence

1. Scoped durable control

identity, projects, session/job tables, unit of work, authorization routes

Real Postgres tests for foreign-account IDs, duplicate keys, competing reservations; S03/S12

2. Reliable work

job claims, epochs, outbox, dispatcher, reconciler, artifact staging

Process-kill tests at transaction boundaries; S04–S08/S22

3. Voice session

transport/provider adapter, runtime coordinator, playback cursor, reconnect

Physical Android interruption/reconnect demonstration; S01/S02/S16

4. Research delivery

bounded search/research capability, report artifacts, delivery coordinator

Call ends mid-job; report survives and reappears without stale speech; S13/S14/S20

5. Correctable memory

extraction, provenance, revisions, vectors, deletion scopes, invalidation

Barrier-controlled deletion/correction races; S09–S11/S21

6. Pilot operations

usage settlement, dashboards, backups, migrations, deployment rollback

Saturation, restore, mixed-version and cost reconciliation exercises; S15/S17–S19

Test harness should use real Postgres/Redis for transactions and crashes, deterministic fake model/transport adapters for ordering, and actual devices/providers for speech timing. SQLite or mocks alone cannot establish lease/locking correctness. Inject barriers immediately before commit, and kill processes rather than only raising handled exceptions.

10. Operational settings to establish before pilot

Numerical settings below are proposed starting points, not measured promises: 30-second reconnect grace; 15-second ownership lease renewed every 5 seconds; 3 attempts maximum for eligible background failures; a 5-second quick-search deadline; a 5-minute research deadline. Tune them together using network/device trials, and apply independent spend ceilings even if time remains.

Measure p50/p95 end-of-speech to first audio, interruption-to-playback-stop, call-start success, reconnect success, job recovery time, memory correction persistence, deletion propagation, and cost by provider attempt. Set launch thresholds from trials; do not invent a latency SLA before a provider/device benchmark.

Remaining decisions: exact voice model and plugin versions, post-call extraction model, API/worker and Redis hosting vendor, regional connectivity, currency budgets and measured concurrency capacity. Prototype retention and latency defaults are already specified; validate feasibility before pilot release. Embedding selection and research quality criteria are deferred with those features. Pin tested SDK/model versions during implementation.

Stack integration rules

Prototype Specification v1.0.1 section 7.1 is the authoritative stack record. Expo/React Native uses local development builds and EAS pilot distribution. LiveKit Agents Python owns orchestration; domain services remain behind interfaces.

Supabase Auth supplies identity; FastAPI verifies it and enforces current account access. Internal schemas are private; exposed tables require grants and RLS. Privileged backend connections do not inherit automatic per-user isolation. Never ship privileged credentials in the mobile app.

SQLAlchemy/psycopg performs transactional database access; Supabase CLI SQL migrations are the only schema history. Do not add Alembic concurrently. Bound all process pools and choose supported direct/session-pooled connectivity.

Sentry handles errors and sampled performance traces; PostHog tracks explicit product events with replay disabled initially. Configure LiveKit/provider telemetry to respect the same content-retention rules. Keep usage and cost authoritative in Postgres.

GitHub Actions runs lint/type checks, pytest, migration and isolation tests; deploys passing builds to staging for smoke checks; triggers EAS internal builds on demand/tags and uploads source maps. Real-device tests remain required separately.

Investigate Mumbai co-location for Supabase, agent and backend. Check media routing and model/telemetry processing separately; region choice is not proof of Indian data residency.

Compare Gemini 3.8 Live and GPT-Live-1 using the same scenarios and scoring with documented adapter-specific settings. Verify account access and exact plugin support. Include delegated reasoning-model, transport and agent costs in comparisons.

Revision 0.2 aligns the stack and marks research/embeddings as deferred for v1. The 22 tabletop scenarios remain design analyses, not newly executed runtime tests.

11. Assessment and sources

Assessment: the modular-monolith direction survives the tabletop review. The essential additions are fenced ownership, source epochs/provenance, atomic publication of outcomes, and independent result delivery. The design is ready to guide a first implementation slice, not certified for production. Highest residual risks are real audio delivery semantics, provider context deletion limits, race implementation correctness, and measured latency/cost under load.

Sources checked for infrastructure semantics; product-specific contracts and mitigations above are proposed engineering decisions:

Redis Pub/Sub delivery semantics: at-most-once messaging; unsuitable as the sole durable job mechanism.

Celery task guide: acknowledgements and idempotency need deliberate configuration; late acknowledgement alone is insufficient.

PostgreSQL constraints: unique/null behavior and limits on cross-row CHECK constraints. This reference is not a requirement to deploy PostgreSQL 18.
