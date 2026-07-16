# Enterprise Ecommerce Agent Upgrade Design

## Objective

Upgrade the current deterministic ecommerce operations demo into a resume-grade hybrid AI agent. DeepSeek provides structured planning and grounded explanation, while deterministic Python tools remain the source of truth for metrics, forecasts, risk decisions, and approval policy. The application must remain fully usable without an API key.

## Scope

The upgrade covers six independently testable areas:

1. Hybrid planning, deterministic fallback, and multi-turn session memory.
2. Ninety-day business data with funnel, RFM, campaign-effect, competitor, and forecast analytics.
3. Durable sessions, runs, tool traces, recommendations, and approval audit records.
4. Runtime observability for latency, tokens, status, errors, and fallback reasons.
5. A repeatable agent evaluation dataset and report.
6. Frontend views for conversations, analytics, approval history, runs, and evaluations.

## Agent Architecture

`HybridEcommerceAgent` receives `question`, `session_id`, and the authenticated user. It loads recent conversation context, requests a structured `AgentPlan` from DeepSeek, validates the plan against a tool allowlist and a six-step limit, executes deterministic tools, and asks DeepSeek to summarize only the returned evidence. Risk level and approval requirements are always calculated by Python policy code.

If the API key is missing, the model times out, or structured output is invalid, the request continues through the deterministic router. Responses expose `execution_mode` and `fallback_reason` so the UI and evaluation suite can distinguish model-backed and fallback runs.

DeepSeek may select tools and extract parameters, but it cannot execute arbitrary code, issue SQL, alter calculated values, approve recommendations, or bypass policy checks.

## Tool Contracts

Every tool returns a normalized result containing `tool_name`, `input`, `metrics`, `evidence`, `summary`, and `warnings`. The registry contains:

- `get_kpi_snapshot`
- `explain_gmv_attribution`
- `analyze_conversion_funnel`
- `analyze_customer_rfm`
- `analyze_campaign_effect`
- `analyze_competitor_price`
- `detect_anomalies`
- `rank_products`
- `forecast_gmv`
- `generate_campaign_plan`

The campaign goal is extracted from natural-language Agent requests and passed to `generate_campaign_plan`; the Agent endpoint and direct campaign endpoint therefore share the same behavior.

## Data And Analytics

The demo generator uses a fixed random seed to create at least 90 days of reproducible products, customers, traffic funnel events, orders, payments/refunds, campaigns, ad spend, inventory, reviews, and competitor prices. CSV/JSON remains the inspectable business-data source.

Analytics include daily/weekly/monthly trends, period-over-period deltas, seven- and thirty-day moving averages, exposure-to-refund funnel conversion, RFM segments, repeat purchase rate, estimated LTV, campaign incremental GMV/cost/ROI, competitor price index, and a deterministic short-horizon GMV forecast. Strategy impact is returned as a range and explicitly labeled as a simulation.

Static demo data is cached after first load. Aggregate caching uses in-process TTL storage by default and may use Redis when configured.

## Persistence

SQLAlchemy models store:

- `agent_sessions`
- `agent_messages`
- `agent_runs`
- `tool_executions`
- `recommendations`
- `approval_records`
- `evaluation_runs`

Development defaults to a local SQLite database. PostgreSQL uses the same repository interfaces in production. Recommendation transitions use an integer version for optimistic concurrency, an idempotency key for duplicate requests, operator identity, comments, timestamps, and an immutable approval audit record.

Database failure must not fabricate persistence. Analysis may return with `persistence_status=failed`, but high-risk actions remain blocked.

## Observability

Each request has a `run_id` and records execution mode, model, planning latency, per-tool latency, summary latency, total latency, token usage, status, fallback reason, and sanitized error data. Secrets and authorization data are never persisted.

The runtime API supports filtering by date, status, execution mode, and tool. Aggregate endpoints expose success rate, fallback rate, latency percentiles, and token totals.

## Frontend

The existing Vue 3 and Element Plus application gains:

- Multi-turn Agent sessions with history, mode, traces, evidence, and streaming progress.
- Ninety-day dashboard trends, funnel, channels, and forecast.
- Customer analysis for RFM, new/returning customers, repeat rate, and LTV.
- Product competitor-price and risk context.
- Campaign planning with simulated impact and post-campaign review.
- Durable approvals with comments and audit timeline.
- Agent run explorer and evaluation dashboard.

The interface retains the current restrained operations-workbench style. No additional heavy UI framework is introduced.

## Streaming And Failure Policy

The synchronous API remains available for compatibility. An SSE endpoint emits planning, tool-start, tool-complete, summarizing, and completed events. LLM calls have a bounded timeout and no long retry loop. Tool failure returns completed evidence plus warnings. Invalid input returns 400. LLM failure falls back. Persistence failure is surfaced. High-risk execution fails closed.

## Testing And Evaluation

Backend TDD covers structured plans, allowlist enforcement, step limits, fallback cases, session restoration, campaign-goal extraction, analytics formulas, durable approvals, optimistic locking, idempotency, traces, and database contracts.

Frontend verification covers session creation/restoration, different campaign goals, fallback display, durable approval refresh, error states, and responsive layout. Playwright covers login through Agent analysis and approval.

The evaluation dataset contains at least 40 questions across diagnosis, ads, inventory, products, campaigns, customers, competitors, follow-ups, irrelevant requests, and unsafe actions. CI uses a deterministic fake planner. Optional online DeepSeek evaluation reports intent accuracy, tool-selection accuracy, parameter accuracy, evidence correctness, risk accuracy, fallback success, mean latency, and P95 latency.

## Engineering Cleanup

Docker services, database defaults, environment examples, and operational documentation use ecommerce naming instead of inherited `rag-*` names. The knowledge base remains available as an auxiliary operations-knowledge module. Documentation must not claim real marketplace integration, production deployment, or measured commercial uplift.

## Acceptance Criteria

- The full demo works without a DeepSeek key and uses real structured planning when a key is configured.
- Conversations and approvals survive backend restart.
- Every new analytic is reproducible and covered by tests.
- Runs, traces, fallback reasons, and evaluation reports are visible through APIs and the frontend.
- Backend tests, frontend type checking/build, and core end-to-end flows pass.
- README, architecture, demo, and resume documentation match the implementation.

