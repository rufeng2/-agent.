# LangGraph And Celery Agent Runtime Design

## Objective

Upgrade the ecommerce Agent runtime to use LangGraph for durable orchestration and Celery for optional background execution. Preserve the existing deterministic tools, local zero-infrastructure demo, synchronous compatibility API, risk policy, and approval workflow.

## Responsibility Boundaries

LangGraph owns Agent state and control flow: context loading, planning, tool execution, partial failure, summarization, policy evaluation, approval interruption, and completion. Celery owns job scheduling: queueing, worker concurrency, hard/soft time limits, retry policy, cancellation signals, and horizontal worker scaling.

Redis is the Celery broker/result backend and event publication channel. PostgreSQL stores sessions, run metadata, tool traces, recommendations, approval audit, workspace ownership, and LangGraph checkpoints. FastAPI creates jobs, exposes status and cancellation APIs, and converts runtime events to SSE.

Celery never implements Agent planning, and LangGraph never owns distributed job scheduling.

## Runtime Modes

`AGENT_EXECUTION_MODE=inline` is the development default. FastAPI invokes the LangGraph graph in-process and publishes events through an in-memory event broker. SQLite stores application state and a LangGraph-compatible checkpoint adapter. Redis, RabbitMQ, and PostgreSQL are not required.

`AGENT_EXECUTION_MODE=celery` sends a job to the `ecommerce_agent` Celery queue. A worker executes the same graph and publishes events to Redis. PostgreSQL is the production persistence target. Startup validation fails closed when Celery mode lacks a broker, result backend, or durable database.

The synchronous `/agent/analyze` endpoint invokes inline execution for compatibility. The asynchronous job API uses the configured runtime mode.

## LangGraph State

`EcommerceAgentState` contains:

- run, session, user, and workspace identifiers
- user question and bounded conversation context
- execution mode and model metadata
- structured plan and current step
- normalized tool results, evidence, warnings, and errors
- prompt/completion token usage and timing
- recommendation drafts and risk level
- cancellation and approval state
- final answer and terminal status

Graph nodes:

1. `load_context`
2. `plan`
3. `validate_plan`
4. `execute_tools`
5. `summarize`
6. `apply_policy`
7. `persist_result`
8. `await_approval` for high-risk execution requests
9. `complete`

Conditional edges route model failures to deterministic planning, tool failures to partial-result summarization, cancellation to a cancelled terminal node, and high-risk execution to an interrupt instead of direct action.

## Function Calling

DeepSeek receives OpenAI-compatible tool definitions generated from Pydantic input models. The model may select only registered tools. Each tool call is parsed into its declared schema before execution. Unknown names, invalid arguments, duplicate call identifiers, more than six calls, or prohibited actions are rejected.

The deterministic planner remains available and produces the same `AgentPlan` contract. Tool calculations, risk levels, impact ranges, and approval requirements remain authoritative Python outputs.

## Job Lifecycle

`POST /api/ecommerce/agent/jobs` creates a run and returns `202` with `job_id`, `run_id`, `session_id`, and `status_url`. An idempotency key prevents duplicate jobs.

`GET /api/ecommerce/agent/jobs/{job_id}` returns queued, running, waiting_approval, completed, failed, or cancelled state.

`DELETE /api/ecommerce/agent/jobs/{job_id}` records cancellation and revokes a Celery task when applicable. Graph nodes check cancellation before every model and tool call. Cancelled jobs do not persist recommendation drafts.

`GET /api/ecommerce/agent/jobs/{job_id}/events` streams ordered SSE events. Clients reconnect with `Last-Event-ID`; persisted event sequence numbers prevent loss or duplication.

## Real-Time Events

Events are emitted when work actually starts or finishes:

- `job_queued`
- `context_loaded`
- `planning_started`
- `plan_ready`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `summarization_started`
- `approval_required`
- `completed`
- `failed`
- `cancelled`

Inline mode uses an asyncio broker with persisted event fallback. Celery mode publishes to Redis Pub/Sub and persists every event before publication. SSE reads persisted history first, then subscribes for new events.

## Workspace Isolation

Authenticated identity comes from the existing JWT dependency. Every session, run, event, recommendation, simulation state, and evaluation run belongs to a `workspace_id`. A user receives a default workspace during first access. Repository queries require both resource ID and workspace ID; resource existence is not revealed across workspaces.

Development requests without a production identity may use a documented local demo user. Production mode forbids the hard-coded demo identity.

## Atomicity And Idempotency

Simulation advance and recommendation approval use conditional SQL updates on `(id, workspace_id, version)`. Zero affected rows produce HTTP 409. Job creation, tool execution, recommendation persistence, and event publication use idempotency keys.

Celery retries resume from the latest checkpoint. Side-effecting nodes check a durable operation key before writing. A retry cannot create duplicate recommendations, approval records, or tool traces.

## Migrations

Alembic revisions add workspaces, workspace foreign keys, agent jobs, agent events, cancellation state, idempotency keys, and checkpoint storage. Existing rows migrate into a default workspace. SQLite tests upgrade a blank database and an existing pre-upgrade fixture. PostgreSQL SQL generation is validated in CI.

`create_all` remains available only for disposable development databases. Production startup requires the schema revision to match Alembic head.

## Frontend

The Agent workspace submits a job, opens an SSE stream, and renders live state without waiting for completion. An `AbortController` cancels the stream and calls the cancellation endpoint. Reconnecting resumes from the latest event ID. The existing synchronous request remains a fallback when job creation is unavailable in development.

The UI shows queued/running/cancelled/waiting-approval states, real tool timing, model/fallback mode, and retry warnings. Controls have stable dimensions and remain usable on mobile.

## Failure Policy

- Model planning failure: deterministic planning fallback.
- Individual tool failure: persist failure event and continue with completed evidence when useful.
- Redis event failure: events remain persisted and SSE polls durable history.
- Celery worker loss: retry from checkpoint.
- Database failure: fail the job; high-risk actions remain closed.
- Cancellation: stop before the next external call and do not create recommendation drafts.
- Duplicate delivery: return the existing idempotent result.

## Testing

Tests cover graph routing, function-call validation, real event ordering, cancellation, reconnect replay, inline/Celery parity, workspace isolation, atomic conflicts, duplicate Celery delivery, checkpoint resume, migration upgrade, and production configuration validation.

Celery tests use eager mode and a fake event publisher. Redis integration tests use the existing Docker profile and are separate from the zero-dependency unit suite. Playwright verifies live event rendering, cancellation, reconnect, and mobile behavior.

## Acceptance Criteria

- LangGraph executes the same deterministic tools and preserves current Agent results.
- Celery and inline modes produce equivalent final outputs and event order.
- SSE emits tool events around actual tool execution, not after completion.
- Cancelling prevents subsequent tool/model calls and recommendation persistence.
- Two workspaces cannot read or mutate each other's resources.
- Concurrent approval and simulation transitions allow only one winner.
- Alembic upgrades both blank and existing schemas.
- The complete demo still runs without Redis, RabbitMQ, PostgreSQL, or a model key.
- Backend tests, frontend build, Agent evaluation, and desktop/mobile E2E pass.
