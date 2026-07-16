import re
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from backend.ecommerce.persistence.repository import EcommerceRepository, VersionConflict
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.mcp_client import EcommerceMCPClient


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


def _event(agent: str, event_type: str, detail: str) -> dict[str, Any]:
    return {"agent": agent, "type": event_type, "detail": detail, "at": datetime.now(timezone.utc).isoformat()}


class LangGraphExecutionAgent:
    def __init__(self, repository: EcommerceRepository, dataset: EcommerceDataset, mcp_client: EcommerceMCPClient | None = None):
        self.repository = repository
        self.dataset = dataset
        self.mcp = mcp_client or EcommerceMCPClient(repository.url)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ExecutionState)
        builder.add_node("supervisor", self._supervisor)
        builder.add_node("catalog_agent", self._catalog_agent)
        builder.add_node("pricing_agent", self._pricing_agent)
        builder.add_node("listing_agent", self._listing_agent)
        builder.add_node("marketing_agent", self._marketing_agent)
        builder.add_node("risk_agent", self._risk_agent)
        builder.add_node("approval_gate", self._approval_gate)
        builder.add_node("tool_executor", self._tool_executor)
        builder.set_entry_point("supervisor")
        builder.add_edge("supervisor", "catalog_agent")
        builder.add_conditional_edges("catalog_agent", lambda state: state["specialist"], {
            "pricing_agent": "pricing_agent", "listing_agent": "listing_agent", "marketing_agent": "marketing_agent",
        })
        builder.add_edge("pricing_agent", "risk_agent")
        builder.add_edge("listing_agent", "risk_agent")
        builder.add_edge("marketing_agent", "risk_agent")
        builder.add_edge("risk_agent", "approval_gate")
        builder.add_edge("approval_gate", "tool_executor")
        builder.add_edge("tool_executor", END)
        return builder.compile(checkpointer=InMemorySaver())

    async def create_task(self, goal: str, workspace_id: str, operator: str):
        task = await self.repository.create_execution_task(workspace_id, operator, goal)
        initial: ExecutionState = {"task_id": task.id, "goal": goal, "workspace_id": workspace_id, "operator": operator, "approved": False, "events": [], "status": "planning"}
        try:
            output = await self.graph.ainvoke(initial, config={"configurable": {"thread_id": task.id}})
            state = await self._current_state(task.id, output)
            return await self.repository.update_execution_task(task.id, workspace_id, status="waiting_approval", state=state, events=state.get("events", []))
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
        await self.repository.update_execution_task(task_id, workspace_id, status="running", expected_version=expected_version)
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
        return await self.repository.update_execution_task(task_id, workspace_id, status="rolled_back", events=events, result={**task.result, "rollback": rollback_result}, expected_version=expected_version)

    async def _current_state(self, task_id: str, output: dict) -> dict:
        snapshot = await self.graph.aget_state({"configurable": {"thread_id": task_id}})
        values = dict(snapshot.values) if snapshot.values else dict(output)
        values.pop("__interrupt__", None)
        return values

    async def _supervisor(self, state: ExecutionState):
        goal = state["goal"].strip()
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
        events = [*state.get("events", []), _event("Supervisor", "task_planned", f"识别为 {action_type}，分派给 {specialist}")]
        return {"action_type": action_type, "specialist": specialist, "product_id": product.product_id, "parameters": parameters, "events": events}

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
        return {"parameters": parameters, "events": [*state["events"], _event("Pricing Agent", "policy_validated", f"调价幅度 {change_pct:.2f}%，预计毛利率 {margin_pct:.2f}%")]}

    async def _listing_agent(self, state: ExecutionState):
        target = "listed" if state["action_type"] == "product_publish" else "unlisted"
        return {"parameters": {**state["parameters"], "listing_status": target}, "events": [*state["events"], _event("Listing Agent", "change_prepared", f"准备将商品状态改为 {target}")]}

    async def _marketing_agent(self, state: ExecutionState):
        budget = round(max(100, min(500, float(state["product"]["price"]) * 1.05)), 2)
        campaign = {"name": f"{state['product']['name']}-{state['parameters']['goal']}", "daily_budget": budget, "target_acos_pct": 35, "channels": ["搜索广告", "商品广告"], "optimization_rule": "连续3天无转化则降价20%"}
        return {"parameters": {**state["parameters"], "campaign": campaign}, "events": [*state["events"], _event("Marketing Agent", "campaign_prepared", f"生成日预算 {budget} 元的推广活动")]}

    async def _risk_agent(self, state: ExecutionState):
        risk = "high" if state["action_type"] in {"price_update", "product_publish", "product_unpublish"} else "medium"
        reason = "该操作会修改商品交易状态，必须人工审批" if risk == "high" else "该操作会创建营销预算，执行前需要确认"
        return {"risk_level": risk, "approval_reason": reason, "status": "waiting_approval", "events": [*state["events"], _event("Risk Agent", "approval_required", reason)]}

    async def _approval_gate(self, state: ExecutionState):
        if not state.get("approved"):
            decision = interrupt({"task_id": state["task_id"], "action_type": state["action_type"], "product": state["product"], "parameters": state["parameters"], "risk_level": state["risk_level"], "reason": state["approval_reason"]})
            if not decision.get("approved"):
                raise PermissionError("任务未获批准")
        return {"approved": True, "events": [*state["events"], _event("Approval Gate", "approved", "人工审批通过，恢复执行图")]}

    async def _tool_executor(self, state: ExecutionState):
        before = dict(state["product"])
        action_type = state["action_type"]
        if action_type == "price_update":
            tool_name = "update_product_price"
            response = await self.mcp.call_tool(tool_name, {"product_id": state["product_id"], "new_price": float(state["parameters"]["new_price"]), "expected_version": int(before["catalog_version"]), "approved_task_id": state["task_id"]})
            after = response["after"]
        elif action_type in {"product_publish", "product_unpublish"}:
            tool_name = "set_product_listing"
            response = await self.mcp.call_tool(tool_name, {"product_id": state["product_id"], "listing_status": state["parameters"]["listing_status"], "expected_version": int(before["catalog_version"]), "approved_task_id": state["task_id"]})
            after = response["after"]
        else:
            tool_name = "create_marketing_campaign"
            campaign = state["parameters"]["campaign"]
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
        if any(word in goal for word in ("营销", "推广", "广告", "活动")):
            return "marketing_plan", "marketing_agent"
        raise ExecutionPlanningError("当前支持上架、下架、调价和创建营销活动，请给出明确执行目标")

    def _match_product(self, goal: str):
        normalized = goal.lower()
        exact = [item for item in self.dataset.products if item.product_id.lower() in normalized or item.name.lower() in normalized]
        if len(exact) == 1:
            return exact[0]
        raise ExecutionPlanningError("无法唯一确定目标商品，请输入商品名称或商品编号")
