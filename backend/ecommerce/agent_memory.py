DEFAULT_AGENT_MEMORIES = {
    "product_research": {"selection_policy": {"blocked_categories": [], "minimum_market_score": 70}},
    "pricing": {"pricing_policy": {"minimum_margin_pct": 35, "maximum_single_change_pct": 20}},
    "listing": {"brand_policy": {"tone": "professional", "forbidden_claims": ["best", "guaranteed", "cure"]}},
    "advertising": {"advertising_policy": {"target_acos_pct": 35, "daily_budget_limit": 500}},
    "customer_service": {"service_policy": {"tone": "empathetic", "refund_requires_approval": True}},
}


def group_memories(items) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for item in items:
        grouped.setdefault(item.agent, {})[item.memory_key] = item.value
    return grouped
