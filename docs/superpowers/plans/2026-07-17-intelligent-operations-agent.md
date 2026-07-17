# Intelligent Ecommerce Operations Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace keyword-triggered fixed workflows with a multi-turn, evidence-driven ecommerce operations agent that asks clarifying questions, analyzes realistic sandbox data, and safely executes approved changes.

**Architecture:** A conversation service persists user turns and a structured `IntentPlan`. The planner classifies requests into read-only analysis, content delivery, business mutation, or automation; missing required slots produce a clarification response instead of a task. Specialist agents consume a shared sandbox tool layer and return a common evidence-backed report, while mutations continue through LangGraph approval gates and MCP tools.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy Async, LangGraph, MCP Python SDK, DeepSeek API, Vue 3, TypeScript, Element Plus, pytest, Playwright.

## Global Constraints

- The sandbox must never claim to connect to a real ecommerce platform.
- Read-only analysis must not create campaigns or request mutation approval.
- Business mutations must remain tenant-isolated, versioned, approval-gated, auditable, and rollback-capable.
- LLM failure must use deterministic fallback with an explicit generation mode.
- Every recommendation must include data evidence and cannot invent competitors, discounts, certifications, or product facts.

---

### Task 1: Conversation and Clarification Protocol

**Files:**
- Create: `backend/ecommerce/conversation.py`
- Modify: `backend/api/ecommerce.py`
- Modify: `backend/ecommerce/persistence/repository.py`
- Test: `tests/test_operations_conversation.py`

**Interfaces:**
- Produces `ConversationReply(status, session_id, message, plan, questions, task)`.
- Consumes a workspace, operator, optional session id, and user message.

- [x] Write failing tests proving ambiguous requests return targeted questions and do not create execution tasks.
- [x] Persist user and assistant turns using `AgentSessionModel` and `AgentMessageModel`.
- [x] Merge clarification answers with pending plan slots and resume planning.
- [x] Expose `POST /api/ecommerce/conversations/messages` and session list/detail endpoints.
- [x] Run `pytest tests/test_operations_conversation.py -q` and commit.

### Task 2: Unified Intent Planner

**Files:**
- Create: `backend/ecommerce/intent_planner.py`
- Modify: `backend/ecommerce/supervisor.py`
- Test: `tests/test_intent_planner.py`

**Interfaces:**
- Produces `IntentPlan(intent, mode, product_id, slots, missing_slots, confidence, reasoning)`.
- Supports `business_diagnosis`, `product_analysis`, `competitive_analysis`, `content_generation`, `marketing_plan`, `ad_optimization`, `customer_operations`, `price_update`, `product_publish`, `product_unpublish`, and `automation_rule`.

- [x] Write a table-driven failing test covering every intent and ambiguous examples.
- [x] Add deterministic high-priority rules for semantically conflicting terms such as “推广文案” versus “创建推广活动”.
- [x] Add DeepSeek JSON normalization and enforce product ids against the catalog.
- [x] Define required slots and clarification questions for each intent.
- [x] Run planner tests and commit.

### Task 3: Sandbox Tool and Evidence Layer

**Files:**
- Create: `backend/ecommerce/operations_tools.py`
- Test: `tests/test_operations_tools.py`

**Interfaces:**
- Produces typed snapshots for KPIs, product performance, competitors, content signals, ads, customers, inventory, and funnel.

- [x] Write failing tests for date windows, product filters, zero denominators, and evidence provenance.
- [x] Implement aggregations using `EcommerceDataset` records and current catalog overrides.
- [x] Return metric, value, period, source, and sample size for every evidence item.
- [x] Run tool tests and commit.

### Task 4: Specialist Agents

**Files:**
- Create: `backend/ecommerce/specialists.py`
- Modify: `backend/ecommerce/execution_graph.py`
- Test: `tests/test_operations_specialists.py`

**Interfaces:**
- Produces `OperationsReport(summary, findings, evidence, opportunities, actions, risks, generation_mode)`.

- [x] Write failing tests for all eight capabilities and verify reports contain evidence.
- [x] Implement business diagnosis, product, competitor, content, marketing, advertising, and customer specialists.
- [x] Ensure analysis routes complete without approval and mutation routes still interrupt.
- [x] Add critic checks for unsupported claims, missing evidence, and conflicting actions.
- [x] Run specialist and graph tests and commit.

### Task 5: Safe Execution and Automation

**Files:**
- Modify: `backend/ecommerce/execution_graph.py`
- Modify: `backend/mcp_servers/ecommerce_server.py`
- Modify: `backend/ecommerce/persistence/repository.py`
- Test: `tests/test_operations_execution.py`

**Interfaces:**
- Mutation plans produce approval snapshots and MCP receipts; automation plans persist disabled-by-default rules until approved.

- [ ] Write failing tests for price/listing/campaign execution, idempotency, validation, compensation, and automation rules.
- [ ] Require role-based approval according to price, budget, and listing risk.
- [ ] Verify postconditions after MCP writes and compensate partial composite failures.
- [ ] Persist execution events and operator identity.
- [ ] Run execution/security tests and commit.

### Task 6: Conversational Frontend

**Files:**
- Modify: `frontend/src/api/client.ts`
- Rewrite: `frontend/src/views/Ecommerce/ExecutionAgentWorkspace.vue`
- Test: `frontend/e2e/ecommerce-agent.spec.ts`

**Interfaces:**
- Renders user/assistant turns for clarification, plan, report, approval, execution, and failure states.

- [x] Add failing Playwright tests for clarification followed by answer and resumed planning.
- [x] Replace task-only composer calls with conversation message calls.
- [x] Render report evidence, recommendations, and explicit sandbox/model source labels.
- [x] Preserve approval confirmation, MCP receipts, rollback, session history, and mobile layout.
- [x] Run build and desktop/mobile Playwright tests and commit.

### Task 7: Verification and Documentation

**Files:**
- Modify: `README.md`

- [ ] Run full pytest, TypeScript build, and Playwright suites.
- [ ] Verify clean cold start on ports 8001 and 5173.
- [ ] Document architecture, supported intents, sample dialogues, sandbox boundaries, and interview discussion points.
- [ ] Run `git diff --check`, commit, and push the branch.
