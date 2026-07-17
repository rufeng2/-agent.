from typing import Any

class OperationsReflectionCritic:
    def review(self, goal: Any, *, evaluation: dict[str, Any], observations: list[dict[str, Any]], spent: float, iteration: int) -> dict[str, Any]:
        progress = min(1.0, max(0.0, float(evaluation.get("actual_change_pct", 0)) / goal.target_change_pct))
        relevant = [item for item in observations if item.get("iteration", iteration) == iteration]
        evidence_count = sum(1 for item in relevant if item.get("output", {}).get("evidence") or item.get("output", {}).get("source"))
        evidence_score = min(1.0, evidence_count / max(1, len(relevant)))
        unsafe = any(item.get("output", {}).get("unsafe") for item in relevant)
        safety_score = 0.0 if unsafe else 1.0
        cost_score = max(0.0, 1 - spent / goal.budget_limit)
        scores = {"goal_progress": round(progress, 2), "evidence": round(evidence_score, 2), "safety": safety_score, "cost_efficiency": round(cost_score, 2)}
        overall = round(0.4 * progress + 0.25 * evidence_score + 0.25 * safety_score + 0.1 * cost_score, 2)
        achieved = bool(evaluation.get("achieved")) and evidence_score >= 0.5 and safety_score == 1
        decision = "accept" if achieved else "stop" if unsafe or spent >= goal.budget_limit else "replan"
        gap = round(goal.target_change_pct - float(evaluation.get("actual_change_pct", 0)), 2)
        return {"iteration": iteration, "decision": decision, "scores": scores, "overall_score": overall, "reason": "目标和证据校验通过" if decision == "accept" else f"目标尚差 {gap} 个百分点", "evidence_steps": [item.get("step_id") for item in relevant], "next_change": "调整内容变体并重新运行沙箱实验" if decision == "replan" else "停止执行"}
