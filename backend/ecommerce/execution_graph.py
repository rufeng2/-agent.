import re
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from backend.ecommerce.persistence.repository import EcommerceRepository, VersionConflict
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.mcp_client import EcommerceMCPClient
from backend.ecommerce.supervisor import StructuredSupervisor
from backend.ecommerce.intent_planner import OperationsIntentPlanner
from backend.ecommerce.specialists import OperationsSpecialistTeam
from backend.ecommerce.capability_registry import OperationsCapabilityRegistry


class ExecutionPlanningError(ValueError):
    pass


class ExecutionState(TypedDict, total=False):
    task_id: str
    goal: str
    workspace_id: str
    operator: str
    action_type: str
    product_id: str
    product: dict[str, Any]
    parameters: dict[str, Any]
    specialist: str
    risk_level: str
    approval_reason: str
    approved: bool
    events: list[dict[str, Any]]
    result: dict[str, Any]
    status: str
    error: str
    steps: list[dict[str, Any]]
    context: list[dict[str, Any]]
    context_stats: dict[str, Any]


def _event(agent: str, event_type: str, detail: str) -> dict[str, Any]:
    return {"agent": agent, "type": event_type, "detail": detail, "at": datetime.now(timezone.utc).isoformat()}


class LangGraphExecutionAgent:
    def __init__(self, repository: EcommerceRepository, dataset: EcommerceDataset, mcp_client: EcommerceMCPClient | None = None, checkpointer=None):
        self.repository = repository
        self.dataset = dataset
        self.mcp = mcp_client or EcommerceMCPClient(repository.url)
        self.supervisor = StructuredSupervisor(dataset)
        self.intent_planner = OperationsIntentPlanner(dataset)
        self.specialists = OperationsSpecialistTeam(dataset)
        self.capabilities = OperationsCapabilityRegistry.default()
        self.checkpointer = checkpointer or InMemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ExecutionState)
        builder.add_node("supervisor", self._supervisor)
        builder.add_node("catalog_agent", self._catalog_agent)
        builder.add_node("pricing_agent", self._pricing_agent)
        builder.add_node("listing_agent", self._listing_agent)
        builder.add_node("marketing_agent", self._marketing_agent)
        builder.add_node("content_agent", self._content_agent)
        builder.add_node("competitor_agent", self._competitor_agent)
        builder.add_node("risk_agent", self._risk_agent)
        builder.add_node("approval_gate", self._approval_gate)
        builder.add_node("tool_executor", self._tool_executor)
        builder.set_entry_point("supervisor")
        builder.add_edge("supervisor", "catalog_agent")
        builder.add_conditional_edges("catalog_agent", lambda state: state["specialist"], {
            "pricing_agent": "pricing_agent", "listing_agent": "listing_agent", "marketing_agent": "marketing_agent", "content_agent": "content_agent", "competitor_agent": "competitor_agent",
        })
        builder.add_edge("pricing_agent", "risk_agent")
        builder.add_edge("listing_agent", "risk_agent")
        builder.add_edge("marketing_agent", "risk_agent")
        builder.add_edge("content_agent", "risk_agent")
        builder.add_edge("competitor_agent", "tool_executor")
        builder.add_edge("risk_agent", "approval_gate")
        builder.add_edge("approval_gate", "tool_executor")
        builder.add_edge("tool_executor", END)
        return builder.compile(checkpointer=self.checkpointer)

    async def create_task(self, goal: str, workspace_id: str, operator: str):
        task = await self.repository.create_execution_task(workspace_id, operator, goal)
        recent = await self.repository.list_execution_tasks(workspace_id, limit=10)
        context = [{"goal": item.goal, "status": item.status, "action_type": item.state.get("action_type"), "result": item.result.get("status", "")} for item in recent if item.id != task.id]
        while len(str(context)) > 8000 and context:
            context.pop()
        initial: ExecutionState = {"task_id": task.id, "goal": goal, "workspace_id": workspace_id, "operator": operator, "approved": False, "events": [], "status": "planning", "context": context, "context_stats": {"items": len(context), "estimated_tokens": len(str(context)) // 4}}
        try:
            output = await self.graph.ainvoke(initial, config={"configurable": {"thread_id": task.id}})
            state = await self._current_state(task.id, output)
            status = "completed" if state.get("status") == "completed" else "waiting_approval"
            return await self.repository.update_execution_task(task.id, workspace_id, status=status, state=state, events=state.get("events", []), result=state.get("result", {}))
        except Exception as exc:
            await self.repository.update_execution_task(task.id, workspace_id, status="failed", error=str(exc))
            raise

    async def approve_and_run(self, task_id: str, workspace_id: str, operator: str, expected_version: int):
        task = await self.repository.get_execution_task(task_id, workspace_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "waiting_approval":
            raise VersionConflict(f"Task is {task.status}, not waiting_approval")
        if task.version != expected_version:
            raise VersionConflict(f"Expected version {expected_version}, found {task.version}")
        approved_state = {
            **task.state,
            "approved": True,
            "approval": {
                "operator": operator,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "action_type": task.state.get("action_type"),
                "product_id": task.state.get("product_id"),
                "parameters": task.state.get("parameters", {}),
            },
        }
        await self.repository.update_execution_task(
            task_id, workspace_id, status="running", state=approved_state,
            expected_version=expected_version,
        )
        config = {"configurable": {"thread_id": task_id}}
        try:
            snapshot = await self.graph.aget_state(config)
            checkpoint_thread = task_id
            if snapshot.next:
                output = await self.graph.ainvoke(Command(resume={"approved": True, "operator": operator}), config=config)
            else:
                recovered = {**task.state, "approved": True, "operator": operator, "events": [*task.events, _event("Approval Gate", "approved", f"{operator} 批准执行")]}
                checkpoint_thread = f"{task_id}-recovered"
                output = await self.graph.ainvoke(recovered, config={"configurable": {"thread_id": checkpoint_thread}})
            state = await self._current_state(checkpoint_thread, output)
            return await self.repository.update_execution_task(task_id, workspace_id, status="completed", state=state, events=state.get("events", []), result=state.get("result", {}))
        except Exception as exc:
            await self.repository.update_execution_task(task_id, workspace_id, status="failed", error=str(exc))
            raise

    async def rollback(self, task_id: str, workspace_id: str, operator: str, expected_version: int):
        task = await self.repository.get_execution_task(task_id, workspace_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "completed" or task.version != expected_version:
            raise VersionConflict("Only the current completed task can be rolled back")
        rollback_state = {
            **task.state,
            "approved": True,
            "approval": {
                "operator": operator,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "action_type": "rollback",
                "product_id": task.result.get("before", {}).get("product_id"),
                "parameters": {},
            },
        }
        prepared = await self.repository.update_execution_task(
            task_id, workspace_id, status="rolling_back", state=rollback_state,
            expected_version=expected_version,
        )
        action_type, before = task.result.get("action_type"), task.result.get("before", {})
        if action_type == "price_update":
            response = await self.mcp.call_tool("rollback_product", {"product_id": before["product_id"], "price": float(before["price"]), "listing_status": None, "expected_version": int(task.result["after"]["catalog_version"]), "approved_task_id": task_id})
            rollback_result = response["after"]
        elif action_type in {"product_publish", "product_unpublish"}:
            response = await self.mcp.call_tool("rollback_product", {"product_id": before["product_id"], "price": None, "listing_status": before["listing_status"], "expected_version": int(task.result["after"]["catalog_version"]), "approved_task_id": task_id})
            rollback_result = response["after"]
        else:
            raise ExecutionPlanningError("营销活动演示回执不支持回滚")
        events = [*task.events, _event("Tool Executor", "mcp_rollback_completed", f"{operator} 通过 MCP 将业务状态恢复到执行前")]
        return await self.repository.update_execution_task(task_id, workspace_id, status="rolled_back", events=events, result={**task.result, "rollback": rollback_result}, expected_version=prepared.version)

    async def _current_state(self, task_id: str, output: dict) -> dict:
        snapshot = await self.graph.aget_state({"configurable": {"thread_id": task_id}})
        values = dict(snapshot.values) if snapshot.values else dict(output)
        values.pop("__interrupt__", None)
        return values

    async def _supervisor(self, state: ExecutionState):
        goal = state["goal"].strip()
        is_composite = any(word in goal for word in ("并创建", "同时创建", "并且创建")) and any(word in goal for word in ("调价", "价格", "降到", "涨到")) and any(word in goal for word in ("营销", "推广", "活动", "广告"))
        operations_plan = self.intent_planner.plan_with_rules(goal)
        if operations_plan.intent == "competitive_analysis" and not operations_plan.missing_slots:
            product = next(item for item in self.dataset.products if item.product_id == operations_plan.product_id)
            events = [*state.get("events", []), _event("Supervisor", "task_planned", "识别为只读竞品分析，分派给 Competitor Agent，不创建活动")]
            return {"action_type": "competitive_analysis", "specialist": "competitor_agent", "product_id": product.product_id, "parameters": operations_plan.slots, "events": events}
        if operations_plan.mode == "mutation" and not operations_plan.missing_slots and not is_composite:
            product = next(item for item in self.dataset.products if item.product_id == operations_plan.product_id)
            action_type = {"marketing_campaign_create": "marketing_plan"}.get(operations_plan.intent, operations_plan.intent)
            specialist = {"price_update": "pricing_agent", "product_publish": "listing_agent", "product_unpublish": "listing_agent", "marketing_plan": "marketing_agent"}[action_type]
            parameters = dict(operations_plan.slots)
            if action_type == "marketing_plan":
                parameters["goal"] = parameters.get("objective", "增长")
            events = [*state.get("events", []), _event("Supervisor", "task_planned", f"结构化业务规划识别为 {action_type}，分派给 {specialist}")]
            return {"action_type": action_type, "specialist": specialist, "product_id": product.product_id, "parameters": parameters, "events": events}
        planner_mode, fallback = "llm", ""
        try:
            llm_plan = await self.supervisor.plan(goal, state.get("context", []))
        except Exception as exc:
            llm_plan, planner_mode, fallback = None, "rules", type(exc).__name__
        if llm_plan is None:
            planner_mode = "rules"
            action_type, specialist = self._classify_action(goal)
            product = self._match_product(goal)
            parameters: dict[str, Any] = {}
            if action_type == "price_update":
                match = re.search(r"(?:调整到|调到|改为|售价为|价格为|降到|涨到|至)\s*[¥￥]?\s*(\d+(?:\.\d+)?)", goal)
                if not match:
                    raise ExecutionPlanningError("调价任务必须给出明确的新价格")
                parameters["new_price"] = float(match.group(1))
            elif action_type == "marketing_plan":
                parameters["goal"] = "新品冷启动" if "新品" in goal or "冷启动" in goal else "大促增长" if "大促" in goal else "日常增长"
        else:
            action_type, parameters = llm_plan.action_type, llm_plan.parameters
            product = next(item for item in self.dataset.products if item.product_id == llm_plan.product_id)
            specialist = {"price_update": "pricing_agent", "product_publish": "listing_agent", "product_unpublish": "listing_agent", "marketing_plan": "marketing_agent", "content_generation": "content_agent"}[action_type]
            if action_type == "price_update" and "new_price" not in parameters:
                raise ExecutionPlanningError("LLM 规划缺少 new_price")
        detail = f"{planner_mode} 识别为 {action_type}，分派给 {specialist}"
        if fallback:
            detail += f"，降级原因 {fallback}"
        events = [*state.get("events", []), _event("Supervisor", "task_planned", detail)]
        steps = []
        if is_composite:
            match = re.search(r"(?:调整到|调到|改为|售价为|价格为|降到|涨到|至)\s*[¥￥]?\s*(\d+(?:\.\d+)?)", goal)
            if not match:
                raise ExecutionPlanningError("复合调价任务必须给出明确的新价格")
            action_type, specialist = "composite", "pricing_agent"
            parameters = {"new_price": float(match.group(1)), "goal": "新品冷启动" if "新品" in goal else "日常增长"}
            steps = [
                {"id": "price", "action_type": "price_update", "status": "pending"},
                {"id": "campaign", "action_type": "marketing_plan", "depends_on": ["price"], "status": "pending"},
            ]
            events[-1] = _event("Supervisor", "dag_planned", "规划复合 DAG：调价 -> 创建营销活动")
        return {"action_type": action_type, "specialist": specialist, "product_id": product.product_id, "parameters": parameters, "steps": steps, "events": events}

    async def _catalog_agent(self, state: ExecutionState):
        snapshot = await self.mcp.call_tool("get_product", {"product_id": state["product_id"]})
        return {"product": snapshot, "events": [*state.get("events", []), _event("Catalog Agent", "mcp_tool_called", f"通过 MCP get_product 读取 {snapshot['name']} 当前状态")]}

    async def _pricing_agent(self, state: ExecutionState):
        product, new_price = state["product"], float(state["parameters"]["new_price"])
        change_pct = (new_price - float(product["price"])) / float(product["price"]) * 100
        margin_pct = (new_price - float(product["cost"])) / new_price * 100
        if abs(change_pct) > 20:
            raise ExecutionPlanningError("单次调价幅度不能超过 20%")
        if new_price <= float(product["cost"]):
            raise ExecutionPlanningError("新价格不能低于商品成本")
        parameters = {**state["parameters"], "old_price": product["price"], "change_pct": round(change_pct, 2), "margin_pct": round(margin_pct, 2)}
        if state.get("action_type") == "composite":
            budget = round(max(100, min(500, new_price * 1.05)), 2)
            parameters["campaign"] = {"name": f"{product['name']}-{parameters['goal']}", "daily_budget": budget, "target_acos_pct": 35, "channels": ["搜索广告", "商品广告"]}
        return {"parameters": parameters, "events": [*state["events"], _event("Pricing Agent", "policy_validated", f"调价幅度 {change_pct:.2f}%，预计毛利率 {margin_pct:.2f}%")]}

    async def _listing_agent(self, state: ExecutionState):
        target = "listed" if state["action_type"] == "product_publish" else "unlisted"
        return {"parameters": {**state["parameters"], "listing_status": target}, "events": [*state["events"], _event("Listing Agent", "change_prepared", f"准备将商品状态改为 {target}")]}

    async def _marketing_agent(self, state: ExecutionState):
        budget = float(state["parameters"].get("daily_budget") or round(max(100, min(500, float(state["product"]["price"]) * 1.05)), 2))
        campaign = {"name": f"{state['product']['name']}-{state['parameters']['goal']}", "daily_budget": budget, "target_acos_pct": 35, "channels": ["搜索广告", "商品广告"], "optimization_rule": "连续3天无转化则降价20%"}
        return {"parameters": {**state["parameters"], "campaign": campaign}, "events": [*state["events"], _event("Marketing Agent", "campaign_prepared", f"生成日预算 {budget} 元的推广活动")]}

    async def _content_agent(self, state: ExecutionState):
        try:
            copy = await self.supervisor.generate_copy(state["goal"], state["product"])
        except Exception as exc:
            product = state["product"]
            channel = "小红书" if "小红书" in state["goal"] else "通用电商"
            copy = {
                "headline": f"{product['name']}，把新鲜带在身边",
                "body": f"为日常通勤、健身和出行准备的{product['name']}，主打{product['positioning']}。随时制作一杯新鲜饮品，让健康补给更简单。",
                "selling_points": [product["positioning"], "适合通勤与出行", "随时享用新鲜饮品"],
                "cta": "立即了解",
                "channel": channel,
                "hashtags": [f"#{product['name']}", "#健康生活", "#通勤好物"],
                "generation_mode": "template",
                "fallback_reason": type(exc).__name__,
            }
        mode = copy["generation_mode"]
        return {"parameters": {**state["parameters"], "copy": copy}, "events": [*state["events"], _event("Content Agent", "copy_generated", f"使用 {mode} 模式生成 {copy['channel']} 推广文案")]}

    async def _competitor_agent(self, state: ExecutionState):
        plan = self.intent_planner.plan_with_rules(state["goal"])
        report = self.specialists.run(plan)
        return {"parameters": {**state["parameters"], "analysis": report}, "events": [*state["events"], _event("Competitor Agent", "analysis_completed", f"读取 {len(report['evidence'])} 组证据完成竞品分析")]}

    async def _risk_agent(self, state: ExecutionState):
        risk = "high" if state["action_type"] in {"price_update", "product_publish", "product_unpublish", "composite"} else "medium"
        reason = "该操作会修改商品交易状态，必须人工审批" if risk == "high" else "文案发布或营销预算执行前需要人工确认"
        change_pct = abs(float(state.get("parameters", {}).get("change_pct", 0)))
        required_role = "admin" if change_pct > 15 else "editor" if change_pct > 10 else "user"
        reason = f"{reason}；要求 {required_role} 级审批"
        return {"risk_level": risk, "approval_reason": reason, "required_approval_role": required_role, "status": "waiting_approval", "events": [*state["events"], _event("Risk Agent", "approval_required", reason)]}

    async def _approval_gate(self, state: ExecutionState):
        if not state.get("approved"):
            decision = interrupt({"task_id": state["task_id"], "action_type": state["action_type"], "product": state["product"], "parameters": state["parameters"], "risk_level": state["risk_level"], "reason": state["approval_reason"]})
            if not decision.get("approved"):
                raise PermissionError("任务未获批准")
        return {"approved": True, "events": [*state["events"], _event("Approval Gate", "approved", "人工审批通过，恢复执行图")]}

    async def _tool_executor(self, state: ExecutionState):
        before = dict(state["product"])
        action_type = state["action_type"]
        if action_type == "competitive_analysis":
            result = {"task_id": state["task_id"], "status": "completed", "environment": "sandbox", "action_type": action_type, "analysis": state["parameters"]["analysis"]}
            return {"status": "completed", "result": result, "events": [*state["events"], _event("Evidence Critic", "report_delivered", "证据字段完整，竞品分析报告已交付，未执行任何写操作")]}
        if action_type == "content_generation":
            result = {"task_id": state["task_id"], "status": "completed", "environment": "sandbox", "action_type": action_type, "product": before, "copy": state["parameters"]["copy"]}
            return {"status": "completed", "result": result, "events": [*state["events"], _event("Tool Executor", "content_delivered", "推广文案已生成并交付，未创建广告活动或产生预算")]}
        if action_type == "composite":
            completed_steps = []
            approval_scope = {"product_id": state["product_id"], "actions": ["price_update", "marketing_plan"]}
            self.capabilities.authorize("Tool Executor", "write_product_price", mode="write", approval_scope=approval_scope)
            price_response = await self.mcp.call_tool("update_product_price", {"product_id": state["product_id"], "new_price": float(state["parameters"]["new_price"]), "expected_version": int(before["catalog_version"]), "approved_task_id": state["task_id"]})
            completed_steps.append({"id": "price", "status": "completed", "result": price_response})
            campaign = state["parameters"]["campaign"]
            try:
                self.capabilities.authorize("Tool Executor", "create_campaign", mode="write", approval_scope=approval_scope)
                campaign_response = await self.mcp.call_tool("create_marketing_campaign", {"product_id": state["product_id"], "name": campaign["name"], "daily_budget": campaign["daily_budget"], "target_acos_pct": campaign["target_acos_pct"], "approved_task_id": state["task_id"]})
                completed_steps.append({"id": "campaign", "status": "completed", "result": campaign_response})
            except Exception:
                await self.mcp.call_tool("rollback_product", {"product_id": state["product_id"], "price": float(before["price"]), "listing_status": None, "expected_version": int(price_response["after"]["catalog_version"]), "approved_task_id": state["task_id"]})
                completed_steps.append({"id": "price_compensation", "status": "completed"})
                raise
            result = {"task_id": state["task_id"], "status": "completed", "environment": "sandbox", "action_type": action_type, "before": before, "after": price_response["after"], "parameters": state["parameters"], "campaign": campaign_response, "steps": completed_steps, "mcp": {"server": "ecommerce-operations", "transport": "stdio", "tools": ["update_product_price", "create_marketing_campaign"]}}
            return {"status": "completed", "result": result, "events": [*state["events"], _event("Tool Executor", "dag_completed", "复合任务 DAG 全部步骤执行成功")]}
        if action_type == "price_update":
            tool_name = "update_product_price"
            self.capabilities.authorize("Tool Executor", "write_product_price", mode="write", approval_scope={"product_id": state["product_id"], "actions": ["price_update"]})
            response = await self.mcp.call_tool(tool_name, {"product_id": state["product_id"], "new_price": float(state["parameters"]["new_price"]), "expected_version": int(before["catalog_version"]), "approved_task_id": state["task_id"]})
            after = response["after"]
        elif action_type in {"product_publish", "product_unpublish"}:
            tool_name = "set_product_listing"
            self.capabilities.authorize("Tool Executor", "write_listing_status", mode="write", approval_scope={"product_id": state["product_id"], "actions": ["listing_update"]})
            response = await self.mcp.call_tool(tool_name, {"product_id": state["product_id"], "listing_status": state["parameters"]["listing_status"], "expected_version": int(before["catalog_version"]), "approved_task_id": state["task_id"]})
            after = response["after"]
        else:
            tool_name = "create_marketing_campaign"
            campaign = state["parameters"]["campaign"]
            self.capabilities.authorize("Tool Executor", "create_campaign", mode="write", approval_scope={"product_id": state["product_id"], "actions": ["marketing_plan"]})
            response = await self.mcp.call_tool(tool_name, {"product_id": state["product_id"], "name": campaign["name"], "daily_budget": campaign["daily_budget"], "target_acos_pct": campaign["target_acos_pct"], "approved_task_id": state["task_id"]})
            after = before
        result = {"task_id": state["task_id"], "status": "completed", "environment": "sandbox", "action_type": action_type, "before": before, "after": after, "parameters": state["parameters"], "mcp": {"server": "ecommerce-operations", "transport": "stdio", "tool": tool_name}}
        if action_type == "marketing_plan":
            result["campaign"] = response
        return {"status": "completed", "result": result, "events": [*state["events"], _event("Tool Executor", "mcp_tool_completed", f"MCP {tool_name} 执行成功并返回回执")]}

    def _classify_action(self, goal: str) -> tuple[str, str]:
        if "下架" in goal:
            return "product_unpublish", "listing_agent"
        if "上架" in goal:
            return "product_publish", "listing_agent"
        if any(word in goal for word in ("调价", "价格调整", "调整价格", "改价", "降价", "涨价")) or ("调整" in goal and "价格" in goal):
            return "price_update", "pricing_agent"
        if any(word in goal for word in ("文案", "标题", "卖点", "种草", "帖子", "广告语")):
            return "content_generation", "content_agent"
        if any(word in goal for word in ("营销", "推广", "广告", "活动")):
            return "marketing_plan", "marketing_agent"
        raise ExecutionPlanningError("当前支持上架、下架、调价、创建营销活动和生成推广文案，请给出明确执行目标")

    def _match_product(self, goal: str):
        normalized = goal.lower()
        exact = [item for item in self.dataset.products if item.product_id.lower() in normalized or item.name.lower() in normalized]
        if len(exact) == 1:
            return exact[0]
        raise ExecutionPlanningError("无法唯一确定目标商品，请输入商品名称或商品编号")
