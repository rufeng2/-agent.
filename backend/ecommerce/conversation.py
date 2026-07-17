import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.ecommerce.intent_planner import IntentPlan, OperationsIntentPlanner
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.specialists import OperationsSpecialistTeam
from backend.ecommerce.autonomous_runtime import AutonomousOperationsRuntime, GoalContractParser


class ConversationReply(BaseModel):
    status: Literal["needs_clarification", "completed", "waiting_approval"]
    session_id: str
    message: str
    plan: IntentPlan
    questions: list[str] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)
    task: dict[str, Any] | None = None


class OperationsConversationService:
    def __init__(self, repository: EcommerceRepository, dataset: EcommerceDataset, execution_agent=None):
        self.repository = repository
        self.planner = OperationsIntentPlanner(dataset)
        self.specialists = OperationsSpecialistTeam(dataset)
        self.execution_agent = execution_agent
        self.goal_parser = GoalContractParser(dataset)
        self.autonomous_runtime = AutonomousOperationsRuntime(repository, dataset)

    async def send(self, message: str, workspace_id: str, operator: str, session_id: str | None = None) -> ConversationReply:
        session = await self.repository.get_session(session_id) if session_id else None
        if session is None:
            session = await self.repository.create_session(workspace_id, message[:80])
        state = self._state(session.summary)
        await self.repository.append_message(session.id, "user", message)
        effective_message = message
        contextual_plan = self._resolve_action_selection(message, state)
        if contextual_plan is not None:
            plan = contextual_plan
            effective_message = f"{state.get('last_message', '')}；执行建议：{state['pending_actions'][plan.slots['selected_action_index']]}"
        elif self._references_previous_actions(message) and state.get("last_report", {}).get("actions"):
            actions = state["last_report"]["actions"]
            response = "我记得上一份报告。请选择要执行的建议动作：\n" + "\n".join(f"{index + 1}. {action}" for index, action in enumerate(actions)) + "\n请回复具体编号，我会复用上一轮的商品、渠道和分析证据继续执行。"
            previous = IntentPlan.model_validate(state["last_plan"])
            clarification = previous.model_copy(update={"missing_slots": ["selected_action"], "questions": [response]})
            await self.repository.update_session_summary(session.id, json.dumps({**state, "pending_actions": actions}, ensure_ascii=False))
            await self.repository.append_message(session.id, "assistant", response)
            return ConversationReply(status="needs_clarification", session_id=session.id, message=response, plan=clarification, questions=[response])
        else:
            plan = None
        if plan is None and state.get("pending_message"):
            effective_message = f"{state['pending_message']}；补充信息：{message}"
        autonomous_request = state.get("pending_autonomous", False) or self._looks_autonomous(effective_message)
        if plan is None and autonomous_request:
            parsed_goal = self.goal_parser.parse(effective_message)
            autonomous_plan = IntentPlan(intent="autonomous_goal", mode="autonomous", product_id=parsed_goal.contract.product_id if parsed_goal.contract else None, slots={"goal": parsed_goal.contract.model_dump() if parsed_goal.contract else {}}, missing_slots=parsed_goal.missing_fields, questions=parsed_goal.questions, confidence=0.98, reasoning="goal contract parser")
            if parsed_goal.contract is None:
                response = "\n".join(parsed_goal.questions)
                await self.repository.update_session_summary(session.id, json.dumps({**state, "pending_message": effective_message, "pending_autonomous": True}, ensure_ascii=False))
                await self.repository.append_message(session.id, "assistant", response)
                return ConversationReply(status="needs_clarification", session_id=session.id, message=response, plan=autonomous_plan, questions=parsed_goal.questions)
            result = await self.autonomous_runtime.run(parsed_goal.contract, workspace_id, operator)
            report = self._autonomous_report(result.model_dump(mode="json"))
            await self.repository.update_session_summary(session.id, json.dumps({"last_message": effective_message, "last_plan": autonomous_plan.model_dump(), "last_report": report}, ensure_ascii=False))
            await self.repository.append_message(session.id, "assistant", json.dumps(report, ensure_ascii=False))
            return ConversationReply(status="completed", session_id=session.id, message=report["summary"], plan=autonomous_plan, report=report)
        if plan is None:
            plan = self.planner.plan_with_rules(effective_message)
        if plan.missing_slots:
            response = "\n".join(plan.questions)
            await self.repository.update_session_summary(session.id, json.dumps({**state, "pending_message": effective_message, "plan": plan.model_dump()}, ensure_ascii=False))
            await self.repository.append_message(session.id, "assistant", response)
            return ConversationReply(status="needs_clarification", session_id=session.id, message=response, plan=plan, questions=plan.questions)

        if plan.mode in {"analysis", "content"}:
            report = self.specialists.run(plan)
            if plan.intent == "content_generation" and self.execution_agent is not None:
                product = await self.execution_agent.mcp.call_tool("get_product", {"product_id": plan.product_id})
                try:
                    copy = await self.execution_agent.supervisor.generate_copy(effective_message, product)
                    report.update({"headline": copy["headline"], "body": copy["body"], "selling_points": copy["selling_points"], "actions": [copy["cta"], *report["actions"]], "generation_mode": "llm", "model": copy.get("model", "")})
                except Exception as exc:
                    report["fallback_reason"] = type(exc).__name__
            response = report["summary"]
            await self.repository.update_session_summary(session.id, json.dumps({"last_message": effective_message, "last_plan": plan.model_dump(), "last_report": report}, ensure_ascii=False))
            await self.repository.append_message(session.id, "assistant", json.dumps(report, ensure_ascii=False))
            return ConversationReply(status="completed", session_id=session.id, message=response, plan=plan, report=report)

        if plan.mode == "automation":
            rule = await self.repository.create_automation_rule(workspace_id, f"{operator}-{plan.intent}", "interval", int(plan.slots["interval_minutes"]), plan.slots["task_prompt"], enabled=False)
            report = {"title": "自动化规则草案", "summary": "规则已保存为禁用状态，需要审批后才能启用。", "findings": [f"运行频率：{plan.slots['schedule']}", f"规则编号：{rule.id}"], "opportunities": ["先手动运行一次并核对输出"], "actions": ["审批规则", "启用后监控首次执行", "异常时立即停用"], "evidence": [{"metric": "automation_enabled", "value": False, "period": "current", "source": "ecommerce_automation_rules", "sample_size": 1}], "generation_mode": "analytics"}
            await self.repository.update_session_summary(session.id, json.dumps({"last_message": effective_message, "last_plan": plan.model_dump(), "last_report": report}, ensure_ascii=False))
            await self.repository.append_message(session.id, "assistant", json.dumps(report, ensure_ascii=False))
            return ConversationReply(status="completed", session_id=session.id, message=report["summary"], plan=plan, report=report)

        if self.execution_agent is None:
            response = "执行参数已完整，等待进入审批工作流。"
            await self.repository.append_message(session.id, "assistant", response)
            return ConversationReply(status="waiting_approval", session_id=session.id, message=response, plan=plan)
        task = await self.execution_agent.create_task(effective_message, workspace_id, operator)
        response = "执行计划已生成，请核对参数并批准。"
        await self.repository.append_message(session.id, "assistant", response)
        return ConversationReply(status="waiting_approval", session_id=session.id, message=response, plan=plan, task={"id": task.id, "status": task.status, "version": task.version})

    @staticmethod
    def _state(summary: str) -> dict:
        try:
            return json.loads(summary or "{}")
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _references_previous_actions(message: str) -> bool:
        return any(phrase in message for phrase in ("你的建议", "上述建议", "上面的建议", "刚才的建议", "这些动作", "建议动作", "这个方案", "刚才的方案"))

    @staticmethod
    def _resolve_action_selection(message: str, state: dict) -> IntentPlan | None:
        actions = state.get("pending_actions", [])
        if not actions:
            return None
        indexes = {"一": 0, "1": 0, "一个": 0, "二": 1, "2": 1, "两个": 1, "三": 2, "3": 2, "三个": 2}
        index = next((value for token, value in indexes.items() if f"第{token}" in message), None)
        if index is None or index >= len(actions):
            return None
        action = actions[index]
        previous = IntentPlan.model_validate(state["last_plan"])
        if any(word in action for word in ("内容", "素材", "文案")):
            slots = {**previous.slots, "selected_action": action, "selected_action_index": index}
            slots.setdefault("channel", previous.slots.get("channel", "通用电商"))
            return IntentPlan(intent="content_generation", mode="content", product_id=previous.product_id, slots=slots, confidence=0.98, reasoning="resolved from previous report action")
        return previous.model_copy(update={"slots": {**previous.slots, "selected_action": action, "selected_action_index": index}, "missing_slots": [], "questions": []})

    @staticmethod
    def _looks_autonomous(message: str) -> bool:
        return any(word in message for word in ("自主", "自动优化", "闭环优化")) or (any(word in message for word in ("提升", "降低", "增长")) and any(word in message for word in ("未来", "预算", "目标")))

    @staticmethod
    def _autonomous_report(result: dict[str, Any]) -> dict[str, Any]:
        evaluation = result.get("evaluation", {})
        reflections = result.get("reflections", [])
        return {
            "title": "自主运营闭环运行报告",
            "summary": f"自主 Agent 完成 {result['iteration']} 轮运行，状态 {result['status']}，累计沙箱成本 ¥{result['spent']}。",
            "findings": [f"KPI：{evaluation.get('metric', '-')}", f"实际变化：{evaluation.get('actual_change_pct', 0)}% / 目标 {evaluation.get('target_change_pct', 0)}%", f"计划版本：v{result['plan']['version']}"],
            "opportunities": [item["next_change"] for item in reflections] or ["当前目标已达到，无需继续重规划"],
            "actions": ["检查每轮 Observation 和 Critique", "确认成功经验已写入情景记忆与 SOP 记忆"],
            "evidence": [{"metric": "kpi_evaluation", "value": evaluation, "period": f"iteration_{result['iteration']}", "source": "autonomous_runtime", "sample_size": len(result.get("observations", []))}],
            "generation_mode": "autonomous_loop",
            "autonomous_run": result,
        }
