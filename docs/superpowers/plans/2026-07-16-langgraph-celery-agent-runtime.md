# LangGraph And Celery Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph-orchestrated ecommerce Agent with optional Celery execution, real SSE events, cancellation, workspace isolation, atomic updates, and migrations.

**Architecture:** One graph executes both inline and Celery jobs. Durable job/event repositories are the source of truth; an event broker only accelerates delivery. Existing deterministic tools and synchronous API remain compatible.

**Tech Stack:** FastAPI, LangGraph, LangChain Core, Celery, Redis, SQLAlchemy asyncio, Alembic, Vue 3, pytest, Playwright.

## Global Constraints

- Local development must run without Redis, RabbitMQ, PostgreSQL, or an LLM key.
- LangGraph owns orchestration; Celery owns scheduling only.
- Unknown tools, more than six calls, and high-risk direct actions are rejected.
- Every repository query is workspace-scoped.
- Cancellation prevents recommendation persistence.

---

### Task 1: LangGraph State And Graph
**Files:** Create `backend/ecommerce/runtime/state.py`, `backend/ecommerce/runtime/graph.py`; modify `backend/requirements-langchain.txt`; test `tests/test_ecommerce_langgraph_runtime.py`.

- [ ] Write failing graph routing, fallback, partial failure, and cancellation tests.
- [ ] Install LangGraph, implement typed state and graph nodes, then rerun focused tests.
- [ ] Commit `feat: orchestrate ecommerce agent with langgraph`.

### Task 2: Function Calling Planner
**Files:** Create `backend/ecommerce/runtime/function_tools.py`; modify `backend/ecommerce/llm.py`, `backend/ecommerce/planning.py`; test `tests/test_ecommerce_function_calling.py`.

- [ ] Test generated schemas, valid calls, unknown calls, invalid arguments, duplicate IDs, and six-call limit.
- [ ] Implement OpenAI-compatible tool definitions and deterministic fallback.
- [ ] Commit `feat: add structured ecommerce function calling`.

### Task 3: Durable Jobs And Real Events
**Files:** Create `backend/ecommerce/runtime/events.py`, `backend/ecommerce/runtime/service.py`; modify persistence models/repository and `backend/api/ecommerce.py`; test `tests/test_ecommerce_agent_jobs.py`.

- [ ] Test actual event timing, ordered replay, reconnect, status, cancellation, and no recommendations after cancellation.
- [ ] Implement job/event persistence, inline runner, SSE replay/subscription, and cancellation API.
- [ ] Commit `feat: add durable realtime agent jobs`.

### Task 4: Celery Scheduling
**Files:** Create `backend/tasks/ecommerce_agent_task.py`; modify `backend/tasks/celery_app.py`, `backend/config.py`; test `tests/test_ecommerce_celery_runtime.py`.

- [ ] Test eager/inline parity, duplicate delivery, retry resume, and production config validation.
- [ ] Implement queue dispatch, checkpoint-aware task, cancellation revoke, and inline fallback.
- [ ] Commit `feat: schedule ecommerce graphs with celery`.

### Task 5: Workspace Isolation And Atomic Updates
**Files:** Modify persistence models/repository, auth dependencies, and ecommerce API; test `tests/test_ecommerce_workspace_isolation.py`, `tests/test_ecommerce_atomic_updates.py`.

- [ ] Test cross-workspace 404, per-workspace simulation/session data, and one-winner concurrent updates.
- [ ] Implement default workspace resolution and conditional SQL updates.
- [ ] Commit `feat: isolate ecommerce workspaces`.

### Task 6: Alembic Migrations
**Files:** Create migration under `backend/db/alembic/versions/`; modify startup schema validation; test `tests/test_ecommerce_migrations.py`.

- [ ] Test blank/existing SQLite upgrade and PostgreSQL-compatible SQL generation.
- [ ] Add workspace, job, event, idempotency, cancellation, and checkpoint migration.
- [ ] Commit `feat: migrate ecommerce agent runtime schema`.

### Task 7: Live Frontend And Cancellation
**Files:** Modify `frontend/src/api/client.ts`, `frontend/src/views/Ecommerce/AgentWorkspace.vue`; test frontend contract and Playwright spec.

- [ ] Test live event display, AbortController cancellation, reconnect ID, and mobile controls.
- [ ] Implement job submission and streaming with synchronous fallback.
- [ ] Commit `feat: stream and cancel agent jobs`.

### Task 8: Verification And Documentation
**Files:** Modify README, architecture, demo, resume, Docker Compose, and environment example.

- [ ] Run full pytest, frontend build, Agent evaluation, and Playwright.
- [ ] Document inline/Celery modes and operational boundaries; run `git diff --check`.
- [ ] Commit `docs: document langgraph celery runtime`.
