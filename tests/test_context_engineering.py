from backend.ecommerce.context_engineering import ContextPacket, OperationsContextBuilder


def test_gssc_context_preserves_policy_state_and_relevant_evidence_within_budget():
    builder = OperationsContextBuilder(max_tokens=180, reserve_ratio=0.1)
    result = builder.build(
        query="继续优化便携榨汁杯转化率",
        policies=["任何价格和活动写操作必须人工审批"],
        task_state={"product_id": "P003", "metric": "conversion_rate", "iteration": 2},
        evidence=[
            ContextPacket("P003 当前转化率 2.1%，来源 funnel.csv", kind="evidence", priority=1, tags=["P003", "conversion_rate"]),
            ContextPacket("P001 防晒衣库存正常", kind="evidence", priority=2, tags=["P001", "inventory"]),
        ],
        memories=[ContextPacket("P003 上次成功 SOP 使用三组内容 A/B 测试", kind="memory", priority=2, tags=["P003", "conversion_rate"])],
        history=["用户之前讨论过 P001", "当前目标是 P003 转化率提升"],
    )

    assert "任何价格和活动写操作必须人工审批" in result.text
    assert "iteration" in result.text
    assert "P003 当前转化率" in result.text
    assert "P003 上次成功 SOP" in result.text
    assert "P001 防晒衣库存正常" not in result.text
    assert result.used_tokens <= result.available_tokens
    assert result.stats["selected"] >= 3
