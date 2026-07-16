# Product Data Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable deterministic advance/reset simulation that changes product metrics consistently across ecommerce APIs.

**Architecture:** A SQLite-backed singleton state stores step, date, seed, events, and product overrides. A pure simulation engine overlays immutable CSV data, and all ecommerce endpoints read through one simulation-aware provider. Vue exposes date, events, controls, and metric deltas.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy asyncio, Vue 3, TypeScript, Element Plus, pytest, Playwright.

## Global Constraints

- Baseline CSV files are never rewritten by runtime simulation.
- The same seed and step produce the same result.
- State survives browser refresh and backend restart.
- Reset restores exact baseline metrics.
- Concurrent stale transitions return HTTP 409.

---

### Task 1: Simulation Engine And State Repository

**Files:**
- Create: `backend/ecommerce/simulation.py`
- Modify: `backend/ecommerce/persistence/models.py`
- Modify: `backend/ecommerce/persistence/repository.py`
- Test: `tests/test_ecommerce_simulation.py`

**Interfaces:**
- Produces `SimulationEngine.apply(dataset, step, seed) -> SimulationResult`.
- Produces repository methods `get_simulation_state`, `advance_simulation`, and `reset_simulation`.

- [ ] Write failing tests for deterministic events, changed metrics, bounds, restart persistence, reset, and stale version conflict.
- [ ] Run `.venv\Scripts\python.exe -m pytest tests/test_ecommerce_simulation.py -q` and verify missing interfaces fail.
- [ ] Implement the pure overlay engine and transactional singleton state.
- [ ] Rerun focused tests and commit `feat: add durable product simulation engine`.

### Task 2: Simulation-Aware Ecommerce APIs

**Files:**
- Modify: `backend/api/ecommerce.py`
- Test: `tests/test_ecommerce_simulation_api.py`

**Interfaces:**
- Adds state, advance, and reset endpoints.
- Changes `_dataset()` to return the current simulation overlay.

- [ ] Write failing API tests for advance, reset, conflict, and consistency across products/dashboard/campaign.
- [ ] Run focused tests and verify endpoint failures.
- [ ] Implement API contracts and shared dataset overlay.
- [ ] Run ecommerce API regressions and commit `feat: expose product simulation api`.

### Task 3: Product Simulation UI

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/Ecommerce/Products.vue`
- Test: `tests/test_ecommerce_frontend_contract.py`

**Interfaces:**
- Adds typed simulation state/advance/reset clients.
- Displays simulation date, events, controls, and per-metric direction/delta.

- [ ] Add failing source contracts for controls, event band, version, and delta fields.
- [ ] Implement controls and stable table delta rendering using existing Element Plus patterns.
- [ ] Run frontend contracts and `npm run build`.
- [ ] Commit `feat: add product simulation controls`.

### Task 4: End-To-End Verification And Documentation

**Files:**
- Modify: `frontend/e2e/ecommerce-agent.spec.ts`
- Modify: `README.md`
- Modify: `docs/demo-script.md`

**Interfaces:**
- E2E advances one day, verifies a changed metric after refresh, then resets baseline.

- [ ] Add the E2E flow and document simulation usage.
- [ ] Run full pytest, frontend build, offline Agent evaluation, and Playwright desktop/mobile tests.
- [ ] Run `git diff --check` and commit `docs: document product simulation workflow`.
