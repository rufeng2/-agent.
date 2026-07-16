from uuid import uuid4

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
            results, traces, evidence = [], [], []
            for step in plan.steps:
                arguments = dict(step.input)
                if step.tool_name == "generate_campaign_plan" and plan.goal and "goal" not in arguments:
                    arguments["goal"] = plan.goal
                result, trace = self.registry.execute(step.tool_name, arguments)
                results.append(result.model_dump())
                traces.append(trace)
                evidence.extend(result.evidence)
            baseline = EcommerceAgent(self.dataset).analyze(question)
            baseline.run_id = run_id
            baseline.execution_mode = "llm"
            baseline.tool_trace = traces
            baseline.evidence = evidence or baseline.evidence
            baseline.summary = await self.planner.summarize(question, results)
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
