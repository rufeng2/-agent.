import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field

from backend.ecommerce.intent_planner import IntentPlan
from backend.ecommerce.operations_tools import SandboxOperationsTools
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.specialists import OperationsSpecialistTeam


class GoalContract(BaseModel):
    objective: str
    product_id: str
    metric: Literal["conversion_rate", "gmv", "ad_roi", "sales"]
    target_change_pct: float = Field(gt=0)
    horizon_days: int = Field(gt=0, le=90)
    budget_limit: float = Field(gt=0)
    max_iterations: int = Field(default=3, ge=1, le=5)
    approval_policy: dict[str, Any] = Field(default_factory=lambda: {"sandbox_experiments": "auto", "business_mutations": "approval_required", "scope_reuse": "low_risk_only"})


class GoalParseResult(BaseModel):
    contract: GoalContract | None = None
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    id: str
    agent: str
    tool: str
    depends_on: list[str] = Field(default_factory=list)
    mode: Literal["read", "sandbox", "write"] = "read"
    status: str = "pending"


class DynamicPlan(BaseModel):
    goal: GoalContract
    version: int = 1
    steps: list[PlanStep]


class AutonomousRunResult(BaseModel):
    task_id: str
    status: Literal["succeeded", "stopped", "failed"]
    iteration: int
    plan: DynamicPlan
    observations: list[dict[str, Any]]
    reflections: list[dict[str, Any]]
    evaluation: dict[str, Any] = Field(default_factory=dict)
    spent: float = 0
    stop_reason: str = ""
    memories_used: list[str] = Field(default_factory=list)


class GoalContractParser:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def parse(self, text: str) -> GoalParseResult:
        product = next((item for item in self.dataset.products if item.product_id.lower() in text.lower() or item.name.lower() in text.lower()), None)
        horizon = re.search(r"(?:未来|近|最近)?\s*(\d+)\s*天", text)
        target = re.search(r"(?:提升|增长|降低|下降)\s*(\d+(?:\.\d+)?)\s*%", text)
        budget = re.search(r"预算(?:上限)?\s*[¥￥]?\s*(\d+(?:\.\d+)?)\s*元?", text)
        metric = "conversion_rate" if "转化" in text else "ad_roi" if any(word in text.upper() for word in ("ROI", "ACOS")) else "gmv" if "GMV" in text.upper() else "sales"
        missing, questions = [], []
        if product is None:
            missing.append("product_id")
            questions.append("这个目标针对哪个商品？请提供商品名称或编号。")
        if target is None:
            missing.append("target")
            questions.append("目标指标希望提升或降低多少百分比？")
        if horizon is None:
            missing.append("horizon_days")
            questions.append("希望在多少天内达成目标？")
        if budget is None:
            missing.append("budget_limit")
            questions.append("本次自主优化允许使用的预算上限是多少元？")
        if missing:
            return GoalParseResult(missing_fields=missing, questions=questions)
        return GoalParseResult(contract=GoalContract(objective=text, product_id=product.product_id, metric=metric, target_change_pct=float(target.group(1)), horizon_days=int(horizon.group(1)), budget_limit=float(budget.group(1))))


class DynamicOperationsPlanner:
    def build(self, goal: GoalContract, version: int = 1) -> DynamicPlan:
        steps = [
            PlanStep(id="baseline", agent="Product Analyst", tool="product_snapshot"),
            PlanStep(id="competitors", agent="Competitor Analyst", tool="competitor_snapshot"),
            PlanStep(id="content", agent="Content Strategist", tool="generate_variants", depends_on=["baseline", "competitors"]),
            PlanStep(id="experiment", agent="Experiment Executor", tool="run_sandbox_experiment", depends_on=["content"], mode="sandbox"),
            PlanStep(id="evaluate", agent="Outcome Evaluator", tool="evaluate_kpi", depends_on=["experiment"]),
        ]
        return DynamicPlan(goal=goal, version=version, steps=steps)

    def replan(self, previous: DynamicPlan, reflection: dict[str, Any]) -> DynamicPlan:
        plan = self.build(previous.goal, previous.version + 1)
        for step in plan.steps:
            if step.id == "content":
                step.tool = "generate_revised_variants"
        return plan


ToolRunner = Callable[[PlanStep, dict[str, Any]], Awaitable[dict[str, Any]]]


class AutonomousOperationsRuntime:
    def __init__(self, repository: EcommerceRepository, dataset: EcommerceDataset, tool_runner: ToolRunner | None = None):
        self.repository = repository
        self.dataset = dataset
        self.tools = SandboxOperationsTools(dataset)
        self.specialists = OperationsSpecialistTeam(dataset)
        self.planner = DynamicOperationsPlanner()
        self.tool_runner = tool_runner or self._run_sandbox_tool

    async def run(self, goal: GoalContract, workspace_id: str, operator: str, task_id: str | None = None) -> AutonomousRunResult:
        task = await self.repository.get_execution_task(task_id, workspace_id) if task_id else await self.repository.create_execution_task(workspace_id, operator, goal.objective)
        if task is None:
            raise KeyError(task_id)
        signature = f"{goal.metric}:{goal.product_id}"
        memories = await self.repository.list_agent_memories(workspace_id, "procedural")
        recalled = next((item for item in memories if item.memory_key == signature and item.source == "memory_consolidator" and item.value.get("evaluation", {}).get("achieved") is True), None)
        memories_used = [signature] if recalled else []
        start_version = int(recalled.value.get("successful_plan_version", 0)) + 1 if recalled else 1
        plan = self.planner.build(goal, start_version)
        observations: list[dict[str, Any]] = []
        reflections: list[dict[str, Any]] = []
        spent = 0.0
        evaluation: dict[str, Any] = {}
        for iteration in range(1, goal.max_iterations + 1):
            state = {"iteration": iteration, "goal": goal.model_dump(), "observations": observations, "spent": spent}
            for step in plan.steps:
                try:
                    output = await self.tool_runner(step, state)
                except Exception as exc:
                    result = AutonomousRunResult(task_id=task.id, status="failed", iteration=iteration, plan=plan, observations=observations, reflections=reflections, evaluation=evaluation, spent=spent, stop_reason=f"tool_error:{step.id}", memories_used=memories_used)
                    await self._persist(task.id, workspace_id, result, error=str(exc))
                    return result
                cost = float(output.get("cost", 0))
                if spent + cost > goal.budget_limit:
                    result = AutonomousRunResult(task_id=task.id, status="stopped", iteration=iteration, plan=plan, observations=observations, reflections=reflections, evaluation=evaluation, spent=spent, stop_reason="budget_limit_exceeded", memories_used=memories_used)
                    await self._persist(task.id, workspace_id, result)
                    return result
                spent += cost
                step.status = "completed"
                observation = {"iteration": iteration, "step_id": step.id, "agent": step.agent, "output": output, "at": datetime.now(timezone.utc).isoformat()}
                observations.append(observation)
                state["observations"] = observations
                state["spent"] = spent
                if step.id == "evaluate":
                    evaluation = self._evaluate(goal, output)
                await self._checkpoint(task.id, workspace_id, goal, plan, iteration, observations, reflections, evaluation, spent, memories_used)
            if evaluation.get("achieved"):
                result = AutonomousRunResult(task_id=task.id, status="succeeded", iteration=iteration, plan=plan, observations=observations, reflections=reflections, evaluation=evaluation, spent=spent, memories_used=memories_used)
                await self._persist(task.id, workspace_id, result)
                await self._consolidate_memory(workspace_id, result)
                return result
            reflection = self._reflect(iteration, evaluation, observations)
            reflections.append(reflection)
            if iteration < goal.max_iterations:
                plan = self.planner.replan(plan, reflection)
                continue
        result = AutonomousRunResult(task_id=task.id, status="stopped", iteration=goal.max_iterations, plan=plan, observations=observations, reflections=reflections, evaluation=evaluation, spent=spent, stop_reason="max_iterations_reached", memories_used=memories_used)
        await self._persist(task.id, workspace_id, result)
        return result

    async def resume(self, task_id: str, workspace_id: str, operator: str) -> AutonomousRunResult:
        task = await self.repository.get_execution_task(task_id, workspace_id)
        if task is None:
            raise KeyError(task_id)
        goal_payload = task.state.get("goal") or task.result.get("plan", {}).get("goal")
        if not goal_payload:
            raise ValueError("task does not contain a resumable autonomous goal")
        return await self.run(GoalContract.model_validate(goal_payload), workspace_id, operator, task_id=task_id)

    async def _run_sandbox_tool(self, step: PlanStep, state: dict[str, Any]) -> dict[str, Any]:
        goal = GoalContract.model_validate(state["goal"])
        if step.id == "baseline":
            return {**self.tools.product_snapshot(goal.product_id, goal.horizon_days), "cost": 0}
        if step.id == "competitors":
            return {**self.tools.competitor_snapshot(goal.product_id, goal.horizon_days), "cost": 0}
        if step.id == "content":
            report = self.specialists.run(IntentPlan(intent="content_generation", mode="content", product_id=goal.product_id, slots={"channel": "沙箱实验"}))
            return {"variants": [report["headline"], f"{report['headline']}·场景版", f"{report['headline']}·利益点版"], "evidence": report["evidence"], "cost": 0}
        if step.id == "experiment":
            return {"experiment_id": f"sandbox-{state['iteration']}", "status": "completed", "cost": min(100, goal.budget_limit * 0.1), "evidence": [{"source": "sandbox_simulation"}]}
        baseline = 2.0
        lift = min(goal.target_change_pct, 7.5 * state["iteration"])
        return {"metric": goal.metric, "baseline": baseline, "current": round(baseline * (1 + lift / 100), 4), "cost": 0, "source": "sandbox_simulation"}

    @staticmethod
    def _evaluate(goal: GoalContract, output: dict[str, Any]) -> dict[str, Any]:
        baseline, current = float(output.get("baseline", 0)), float(output.get("current", 0))
        actual_change = (current - baseline) / baseline * 100 if baseline else 0
        return {"metric": goal.metric, "baseline": baseline, "current": current, "target_change_pct": goal.target_change_pct, "actual_change_pct": round(actual_change, 2), "achieved": actual_change + 1e-9 >= goal.target_change_pct}

    @staticmethod
    def _reflect(iteration: int, evaluation: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
        gap = round(float(evaluation.get("target_change_pct", 0)) - float(evaluation.get("actual_change_pct", 0)), 2)
        return {"iteration": iteration, "decision": "replan", "reason": f"目标尚差 {gap} 个百分点", "evidence_steps": [item["step_id"] for item in observations if item["iteration"] == iteration], "next_change": "调整内容变体并重新运行沙箱实验"}

    async def _persist(self, task_id: str, workspace_id: str, result: AutonomousRunResult, error: str = "") -> None:
        status = "completed" if result.status == "succeeded" else result.status
        payload = result.model_dump(mode="json")
        await self.repository.update_execution_task(task_id, workspace_id, status=status, state={"autonomous": True, "goal": payload["plan"]["goal"], "iteration": result.iteration, "plan": payload["plan"], "reflections": payload["reflections"], "resumable": result.status == "failed"}, events=result.observations, result=payload, error=error)

    async def _checkpoint(self, task_id: str, workspace_id: str, goal: GoalContract, plan: DynamicPlan, iteration: int, observations: list[dict[str, Any]], reflections: list[dict[str, Any]], evaluation: dict[str, Any], spent: float, memories_used: list[str]) -> None:
        await self.repository.update_execution_task(task_id, workspace_id, status="running", state={"autonomous": True, "goal": goal.model_dump(), "iteration": iteration, "plan": plan.model_dump(), "reflections": reflections, "spent": spent, "memories_used": memories_used, "resumable": True}, events=observations, result={"evaluation": evaluation})

    async def _consolidate_memory(self, workspace_id: str, result: AutonomousRunResult) -> None:
        await self.repository.upsert_agent_memory(workspace_id, "episodic", result.task_id, {"goal": result.plan.goal.model_dump(), "evaluation": result.evaluation, "spent": result.spent}, "autonomous_run")
        signature = f"{result.plan.goal.metric}:{result.plan.goal.product_id}"
        await self.repository.upsert_agent_memory(workspace_id, "procedural", signature, {"successful_plan_version": result.plan.version, "steps": [step.model_dump() for step in result.plan.steps], "evaluation": result.evaluation}, "memory_consolidator")
        product = next(item for item in self.dataset.products if item.product_id == result.plan.goal.product_id)
        await self.repository.upsert_agent_memory(workspace_id, "semantic", f"product:{product.product_id}", {"name": product.name, "category": product.category, "positioning": product.positioning, "cost": product.cost}, "catalog_fact")
        await self.repository.upsert_agent_memory(workspace_id, "preference", "autonomous_budget", {"last_budget_limit": result.plan.goal.budget_limit, "approval_policy": result.plan.goal.approval_policy}, "observed_user_constraint")
