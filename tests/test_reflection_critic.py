from backend.ecommerce.autonomous_runtime import GoalContract
from backend.ecommerce.reflection_critic import OperationsReflectionCritic


def test_critic_scores_progress_evidence_safety_and_cost_then_replans():
    goal = GoalContract(objective="提升P003转化", product_id="P003", metric="conversion_rate", target_change_pct=15, horizon_days=7, budget_limit=1000)
    reflection = OperationsReflectionCritic().review(
        goal,
        evaluation={"actual_change_pct": 7.5, "target_change_pct": 15, "achieved": False},
        observations=[{"step_id": "baseline", "output": {"evidence": [{"source": "funnel.csv"}]}}, {"step_id": "experiment", "output": {"evidence": [{"source": "sandbox"}]}}],
        spent=100,
        iteration=1,
    )

    assert reflection["decision"] == "replan"
    assert reflection["scores"]["goal_progress"] == 0.5
    assert reflection["scores"]["evidence"] == 1.0
    assert reflection["scores"]["safety"] == 1.0
    assert 0 <= reflection["overall_score"] <= 1
