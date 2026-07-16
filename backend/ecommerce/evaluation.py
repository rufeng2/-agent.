import inspect
import time
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from backend.ecommerce.observability import percentile


class EvaluationCase(BaseModel):
    id: str
    category: str
    question: str
    expected_intent: str
    expected_tools: list[str]
    expected_goal: str = ""
    expected_risk: str


class EvaluationReport(BaseModel):
    total_cases: int
    intent_accuracy: float
    tool_accuracy: float
    parameter_accuracy: float
    evidence_accuracy: float
    risk_accuracy: float
    fallback_success_rate: float
    mean_latency_ms: float
    p95_latency_ms: float
    failures: list[dict]


async def evaluate_cases(cases: list[EvaluationCase], analyze: Callable[[EvaluationCase], Awaitable[dict] | dict]) -> EvaluationReport:
    scores = {name: 0 for name in ("intent", "tool", "parameter", "evidence", "risk", "fallback")}
    latencies, failures = [], []
    for case in cases:
        started = time.perf_counter()
        value = analyze(case)
        result = await value if inspect.isawaitable(value) else value
        latencies.append((time.perf_counter() - started) * 1000)
        tool_steps = result.get("tool_trace", [])
        tools = {item.get("tool_name") for item in tool_steps}
        goals = {str(item.get("input", {}).get("goal", "")) for item in tool_steps}
        checks = {
            "intent": result.get("intent") == case.expected_intent,
            "tool": set(case.expected_tools) <= tools,
            "parameter": not case.expected_goal or case.expected_goal in goals,
            "evidence": bool(result.get("evidence")),
            "risk": result.get("risk_level") == case.expected_risk,
            "fallback": result.get("execution_mode") in {"llm", "deterministic_fallback", "deterministic"},
        }
        for name, passed in checks.items():
            scores[name] += int(passed)
        if not all(checks.values()):
            failures.append({"id": case.id, "category": case.category, "checks": checks})
    total = len(cases)
    rate = lambda name: round(scores[name] / total * 100, 2) if total else 0
    return EvaluationReport(
        total_cases=total, intent_accuracy=rate("intent"), tool_accuracy=rate("tool"),
        parameter_accuracy=rate("parameter"), evidence_accuracy=rate("evidence"),
        risk_accuracy=rate("risk"), fallback_success_rate=rate("fallback"),
        mean_latency_ms=round(sum(latencies) / total, 2) if total else 0,
        p95_latency_ms=percentile(latencies, 0.95), failures=failures,
    )
