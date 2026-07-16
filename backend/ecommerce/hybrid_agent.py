from uuid import uuid4
import time

from pydantic import ValidationError

from backend.ecommerce.agent import EcommerceAgent
from backend.ecommerce.llm import Planner, configured_planner
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.tool_registry import EcommerceToolRegistry
from backend.ecommerce.tools import EcommerceTools


class HybridEcommerceAgent:
    def __init__(self, dataset: EcommerceDataset, planner: Planner | None = None, use_configured_planner: bool = False):
        self.dataset = dataset
        self.planner = configured_planner() if use_configured_planner else planner
        self.registry = EcommerceToolRegistry(EcommerceTools(dataset))

    async def analyze(self, question: str, session_id: str = "", user_id: str = "demo-user", context: list[dict] | None = None):
        run_id = str(uuid4())
        if self.planner is None:
            return self._fallback(question, run_id, "llm_not_configured")
        try:
            plan = await self.planner.plan(question, context or [])
            results, traces, evidence, warnings = [], [], [], []
            for step in plan.steps:
                arguments = dict(step.input)
                if step.tool_name == "generate_campaign_plan" and plan.goal and "goal" not in arguments:
                    arguments["goal"] = plan.goal
                started = time.perf_counter()
                try:
                    result, trace = self.registry.execute(step.tool_name, arguments)
                except Exception as exc:
                    warnings.append(f"{step.tool_name}: {type(exc).__name__}")
                    continue
                trace.latency_ms = round((time.perf_counter() - started) * 1000, 2)
                results.append(result.model_dump())
                traces.append(trace)
                evidence.extend(result.evidence)
            if not results:
                return self._fallback(question, run_id, "all_tools_failed")
            baseline = EcommerceAgent(self.dataset).analyze(question)
            baseline.run_id = run_id
            baseline.execution_mode = "llm"
            baseline.tool_trace = traces
            baseline.evidence = evidence or baseline.evidence
            baseline.summary = await self.planner.summarize(question, results)
            baseline.prompt_tokens = int(getattr(self.planner, "prompt_tokens", 0))
            baseline.completion_tokens = int(getattr(self.planner, "completion_tokens", 0))
            baseline.warnings = warnings
            return baseline
        except TimeoutError:
            return self._fallback(question, run_id, "llm_timeout")
        except (ValidationError, ValueError, KeyError, TypeError):
            return self._fallback(question, run_id, "invalid_llm_plan")
        except Exception:
            return self._fallback(question, run_id, "llm_unavailable")

    def _fallback(self, question: str, run_id: str, reason: str):
        result = EcommerceAgent(self.dataset).analyze(question)
        result.run_id = run_id
        result.execution_mode = "deterministic_fallback"
        result.fallback_reason = reason
        return result
