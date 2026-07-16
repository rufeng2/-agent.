# Enterprise Ecommerce Agent Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the ecommerce demo into a durable hybrid DeepSeek agent with multi-turn memory, advanced analytics, observability, evaluation, and complete frontend workflows.

**Architecture:** DeepSeek produces validated structured plans and grounded summaries; allowlisted Python tools own all calculations and policy. SQLite is the zero-dependency development store and PostgreSQL is the production store through shared SQLAlchemy repositories. Every model failure degrades to the existing deterministic route.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy asyncio, DeepSeek OpenAI-compatible API, Vue 3, TypeScript, Element Plus, pytest, Playwright, Docker Compose.

## Global Constraints

- The complete demo must run without `DEEPSEEK_API_KEY`.
- Agent plans may call only registered tools and contain at most six steps.
- LLM output cannot determine metric values, approval policy, or risk level.
- Development defaults to SQLite; production supports PostgreSQL with the same repositories.
- Generated business data uses a fixed seed and covers at least 90 days.
- High-risk actions fail closed when persistence or policy checks fail.
- UI copy must label projected impact as simulated.

---

### Task 1: Reproducible 90-Day Dataset

**Files:**
- Create: `scripts/generate_ecommerce_data.py`
- Create: `data/ecommerce/customers.csv`
- Create: `data/ecommerce/funnel.csv`
- Create: `data/ecommerce/campaigns.csv`
- Modify: `backend/ecommerce/schemas.py`
- Modify: `backend/ecommerce/data_loader.py`
- Test: `tests/test_ecommerce_data_generation.py`

**Interfaces:**
- Produces `generate_dataset(output: Path, days: int = 90, seed: int = 20260716) -> None`.
- Extends `EcommerceDataset` with customers, funnel rows, and campaign rows.

- [ ] Write tests asserting 90 distinct dates, deterministic file hashes, referential integrity, and successful Pydantic loading.
- [ ] Run `.venv\Scripts\python.exe -m pytest tests/test_ecommerce_data_generation.py -q` and verify the missing generator/schema failure.
- [ ] Implement the seeded generator and schema/loader extensions.
- [ ] Generate checked-in demo files and rerun the focused test.
- [ ] Run the ecommerce regression tests and commit `feat: add reproducible ecommerce history`.

### Task 2: Advanced Analytics Tools

**Files:**
- Create: `backend/ecommerce/funnel.py`
- Create: `backend/ecommerce/customers.py`
- Create: `backend/ecommerce/campaign_effect.py`
- Create: `backend/ecommerce/competitors.py`
- Create: `backend/ecommerce/forecast.py`
- Modify: `backend/ecommerce/schemas.py`
- Modify: `backend/ecommerce/tools.py`
- Test: `tests/test_ecommerce_advanced_analytics.py`

**Interfaces:**
- Produces `analyze_funnel`, `analyze_rfm`, `analyze_campaign_effect`, `analyze_competitor_prices`, and `forecast_gmv` pure functions.
- Tool methods return normalized `ToolResult(tool_name, input, metrics, evidence, summary, warnings)`.

- [ ] Write formula-based tests with small explicit fixtures for every analytic.
- [ ] Run the focused tests and verify imports/functions are missing.
- [ ] Implement pure analytics and normalized tool adapters.
- [ ] Verify focused and existing metric/agent tests.
- [ ] Commit `feat: add advanced ecommerce analytics`.

### Task 3: Cached Data And Aggregates

**Files:**
- Modify: `backend/ecommerce/data_loader.py`
- Create: `backend/ecommerce/cache.py`
- Test: `tests/test_ecommerce_cache.py`

**Interfaces:**
- Produces `EcommerceDataLoader.load_cached()` and `TTLCache.get_or_set(key, factory)`.

- [ ] Test that unchanged files load once, file modification invalidates the dataset, and TTL expiration recomputes aggregates.
- [ ] Verify RED, implement minimal thread-safe caches, and verify GREEN.
- [ ] Update ecommerce API dependencies to use cached loading.
- [ ] Run API timing contract and regression tests.
- [ ] Commit `perf: cache ecommerce datasets and aggregates`.

### Task 4: Durable Agent Store

**Files:**
- Create: `backend/ecommerce/persistence/models.py`
- Create: `backend/ecommerce/persistence/database.py`
- Create: `backend/ecommerce/persistence/repository.py`
- Create: `backend/ecommerce/persistence/__init__.py`
- Modify: `backend/config.py`
- Test: `tests/test_ecommerce_persistence.py`

**Interfaces:**
- Produces async repositories for sessions, messages, runs, tool executions, recommendations, approvals, and evaluation runs.
- `transition_recommendation(id, target, expected_version, operator, comment, idempotency_key)` is atomic.

- [ ] Test restart persistence with a temporary SQLite file, duplicate idempotency keys, and optimistic-lock conflicts.
- [ ] Verify RED and implement SQLAlchemy models/repositories.
- [ ] Add `ECOMMERCE_DATABASE_URL=sqlite+aiosqlite:///./data/ecommerce_agent.db` and install `aiosqlite`.
- [ ] Verify focused tests and PostgreSQL-compatible metadata types.
- [ ] Commit `feat: persist ecommerce agent workflows`.

### Task 5: Hybrid Planner And Deterministic Fallback

**Files:**
- Create: `backend/ecommerce/planning.py`
- Create: `backend/ecommerce/llm.py`
- Create: `backend/ecommerce/tool_registry.py`
- Create: `backend/ecommerce/hybrid_agent.py`
- Modify: `backend/config.py`
- Modify: `backend/ecommerce/agent.py`
- Test: `tests/test_ecommerce_hybrid_agent.py`

**Interfaces:**
- `AgentPlan(intent, goal, steps)` validates allowlisted tools and six-step maximum.
- `HybridEcommerceAgent.analyze(question, session_id, user_id)` returns execution mode, fallback reason, run ID, trace, evidence, and recommendations.

- [ ] Test valid model plans, unknown tools, seven-step plans, missing key, timeout, malformed JSON, and natural-language campaign goals.
- [ ] Verify RED using a fake planner injected through a protocol.
- [ ] Implement OpenAI-compatible DeepSeek structured output, validator, registry, and deterministic fallback.
- [ ] Confirm the model cannot overwrite tool metrics or risk policy.
- [ ] Run all Agent/API tests and commit `feat: add hybrid DeepSeek ecommerce agent`.

### Task 6: Multi-Turn Sessions And Durable Approvals API

**Files:**
- Modify: `backend/api/ecommerce.py`
- Modify: `backend/ecommerce/schemas.py`
- Remove use of: `backend/ecommerce/recommendations.py` in ecommerce API
- Test: `tests/test_ecommerce_sessions_api.py`
- Test: `tests/test_ecommerce_approvals_api.py`

**Interfaces:**
- Adds session create/list/detail and message analyze endpoints.
- Approval requests require expected version, comment, and idempotency key.

- [ ] Test follow-up context, session restoration with a new app/repository instance, approval audit history, duplicate requests, and conflict responses.
- [ ] Verify RED and implement async API/repository wiring.
- [ ] Keep the old analyze route as a compatibility wrapper.
- [ ] Verify API contracts and commit `feat: add durable agent sessions and approvals`.

### Task 7: Streaming And Partial Failure

**Files:**
- Create: `backend/ecommerce/events.py`
- Modify: `backend/api/ecommerce.py`
- Modify: `backend/ecommerce/hybrid_agent.py`
- Test: `tests/test_ecommerce_agent_stream.py`

**Interfaces:**
- Adds SSE events `planning`, `tool_start`, `tool_complete`, `summarizing`, `completed`, and `warning`.

- [ ] Test event order, disconnect cleanup, LLM fallback events, and a failed tool returning completed evidence plus warning.
- [ ] Verify RED and implement async event generation.
- [ ] Ensure the synchronous compatibility endpoint uses the same execution core.
- [ ] Verify stream and regression tests.
- [ ] Commit `feat: stream ecommerce agent execution`.

### Task 8: Runtime Observability

**Files:**
- Create: `backend/ecommerce/observability.py`
- Modify: `backend/api/ecommerce.py`
- Test: `tests/test_ecommerce_observability.py`

**Interfaces:**
- Adds run list/detail/summary APIs with status, mode, latency, token, tool, and date filters.
- Sanitizer removes API keys, authorization values, and secrets before persistence.

- [ ] Test timing records, token totals, fallback rate, P95, filters, and secret redaction.
- [ ] Verify RED, implement recorder and APIs, then verify GREEN.
- [ ] Run production security tests.
- [ ] Commit `feat: trace ecommerce agent runtime`.

### Task 9: Agent Evaluation Harness

**Files:**
- Create: `data/ecommerce/evaluation_cases.json`
- Create: `backend/ecommerce/evaluation.py`
- Create: `scripts/evaluate_ecommerce_agent.py`
- Modify: `backend/api/ecommerce.py`
- Test: `tests/test_ecommerce_evaluation.py`

**Interfaces:**
- Evaluates at least 40 cases and reports intent, tool, parameter, evidence, risk, fallback, mean latency, and P95 metrics.

- [ ] Test case count/category coverage and exact scoring using a deterministic fake planner.
- [ ] Verify RED and implement evaluator, persistence, CLI, and report APIs.
- [ ] Add optional online mode gated by `DEEPSEEK_API_KEY` and excluded from CI.
- [ ] Verify deterministic report generation.
- [ ] Commit `feat: evaluate ecommerce agent quality`.

### Task 10: Frontend Agent, Analytics, And Approval Workflows

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/Ecommerce/AgentWorkspace.vue`
- Modify: `frontend/src/views/Ecommerce/Dashboard.vue`
- Modify: `frontend/src/views/Ecommerce/Products.vue`
- Modify: `frontend/src/views/Ecommerce/Campaigns.vue`
- Modify: `frontend/src/views/Ecommerce/Recommendations.vue`
- Create: `frontend/src/views/Ecommerce/Customers.vue`
- Create: `frontend/src/views/Ecommerce/Runs.vue`
- Create: `frontend/src/views/Ecommerce/AgentEvaluation.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/App.vue`
- Test: `tests/test_ecommerce_frontend_contract.py`

**Interfaces:**
- Typed API methods mirror all new backend endpoints.
- Agent workspace supports session history and SSE progress with fallback to synchronous requests.

- [ ] Add failing source contracts for routes, session controls, execution-mode badges, simulated-impact labels, audit timeline, and run/evaluation filters.
- [ ] Implement typed clients and views using existing Element Plus patterns.
- [ ] Run `npm run build` and fix all type/layout errors.
- [ ] Verify desktop/mobile screenshots for overlap and stable controls.
- [ ] Commit `feat: expose enterprise agent workflows`.

### Task 11: End-To-End And Performance Verification

**Files:**
- Create: `frontend/e2e/ecommerce-agent.spec.ts`
- Modify: `frontend/package.json`
- Create: `tests/test_ecommerce_performance.py`

**Interfaces:**
- Playwright covers registration, session analysis, goal-specific campaign products, approval persistence, and run inspection.

- [ ] Write E2E and API latency tests before any supporting changes.
- [ ] Verify failures, add only required test setup, and rerun.
- [ ] Confirm deterministic endpoints remain below the local latency budget and LLM fallback is bounded.
- [ ] Commit `test: cover ecommerce agent end to end`.

### Task 12: Deployment Naming And Documentation

**Files:**
- Modify: `backend/config.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.production.yml`
- Modify: `README.md`
- Modify: `docs/demo-script.md`
- Modify: `docs/resume.md`
- Create: `docs/architecture.md`
- Test: `tests/test_ecommerce_docs.py`
- Test: `tests/test_deployment_contract.py`

**Interfaces:**
- Ecommerce service/database/container names replace inherited RAG names while the knowledge module remains documented as auxiliary.

- [ ] Add failing contracts rejecting stale primary-service naming and unsupported resume claims.
- [ ] Update configuration, Compose, and documentation.
- [ ] Run backend full suite, frontend build, E2E suite, and `git diff --check`.
- [ ] Confirm clean runtime startup without external services or DeepSeek key.
- [ ] Commit `docs: finish enterprise ecommerce agent upgrade`.

