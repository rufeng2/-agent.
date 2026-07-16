import json

from pydantic import BaseModel, ValidationError

from backend.ecommerce.planning import AgentPlan, PlannedTool, ToolName


class FunctionCall(BaseModel):
    call_id: str
    tool_name: ToolName
    arguments: dict[str, str | int | float | bool]


def function_tool_definitions() -> list[dict]:
    names = [name for name in AgentPlan.model_fields["steps"].metadata[0].__args__] if False else [
        "get_kpi_snapshot", "explain_gmv_attribution", "analyze_conversion_funnel", "analyze_customer_rfm",
        "analyze_campaign_effect", "analyze_competitor_price", "detect_anomalies", "rank_products",
        "forecast_gmv", "generate_campaign_plan",
    ]
    return [{"type": "function", "function": {"name": name, "description": f"执行{name}电商分析工具", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}}, "additionalProperties": False}}} for name in names]


def parse_function_calls(raw_calls: list[dict]) -> list[PlannedTool]:
    if not raw_calls or len(raw_calls) > 6:
        raise ValueError("function call count must be between 1 and 6")
    parsed = []
    call_ids = set()
    for raw in raw_calls:
        call_id = str(raw.get("id", ""))
        function = raw.get("function", raw)
        if not call_id or call_id in call_ids:
            raise ValueError("function call id must be unique")
        call_ids.add(call_id)
        try:
            name = function["name"]
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            call = FunctionCall(call_id=call_id, tool_name=name, arguments=arguments)
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError("invalid function call") from exc
        parsed.append(PlannedTool(tool_name=call.tool_name, input=call.arguments))
    return parsed
