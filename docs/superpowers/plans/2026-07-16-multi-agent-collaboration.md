# Ecommerce Multi-Agent Collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Supervisor-led ecommerce multi-agent graph with specialist tool permissions, risk review, and report synthesis.

**Architecture:** Add focused collaboration models and specialist agents around the existing deterministic tool registry. Replace the single LangGraph execution node with routing, specialist execution, review, and synthesis while preserving `AgentAnalysis` compatibility.

**Tech Stack:** Python 3.11, Pydantic, LangGraph, pytest, Vue 3.

## Global Constraints

- Reuse existing analytics and persistence implementations.
- Preserve existing API response fields.
- Operate without an LLM API key.
- Reject tools outside each specialist whitelist.

### Task 1: Collaboration contracts and routing

**Files:** `backend/ecommerce/multi_agent.py`, `backend/ecommerce/schemas.py`, `tests/test_ecommerce_multi_agent.py`

- [ ] Write tests for multi-specialist routing and tool permission rejection.
- [ ] Run tests and verify missing implementation failure.
- [ ] Implement role definitions, reports, deterministic Supervisor routing, and specialist execution.
- [ ] Run focused tests.

### Task 2: LangGraph collaboration flow

**Files:** `backend/ecommerce/runtime/state.py`, `backend/ecommerce/runtime/graph.py`, `tests/test_ecommerce_multi_agent.py`, `tests/test_ecommerce_langgraph_runtime.py`

- [ ] Write a failing end-to-end collaboration trace test.
- [ ] Add supervisor, specialists, risk review, and report nodes.
- [ ] Preserve cancellation and final `AgentAnalysis` output.
- [ ] Run runtime regression tests.

### Task 3: UI, documentation, and verification

**Files:** `frontend/src/views/Ecommerce/AgentWorkspace.vue`, `README.md`

- [ ] Display the Agent collaboration trace.
- [ ] Document role boundaries and execution flow.
- [ ] Run full pytest, frontend build, and diff checks.
- [ ] Commit and push the implementation.
