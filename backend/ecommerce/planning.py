from typing import Literal

from pydantic import BaseModel, Field


ToolName = Literal[
    "get_kpi_snapshot", "explain_gmv_attribution", "analyze_conversion_funnel",
    "analyze_customer_rfm", "analyze_campaign_effect", "analyze_competitor_price",
    "detect_anomalies", "rank_products", "forecast_gmv", "generate_campaign_plan",
]


class PlannedTool(BaseModel):
    tool_name: ToolName
    input: dict[str, str | int | float | bool] = Field(default_factory=dict)


class AgentPlan(BaseModel):
    intent: str
    goal: str = ""
    steps: list[PlannedTool] = Field(min_length=1, max_length=6)
