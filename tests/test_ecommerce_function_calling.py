import pytest

from backend.ecommerce.runtime.function_tools import function_tool_definitions, parse_function_calls


def test_function_definitions_cover_registered_tools():
    definitions = function_tool_definitions()
    assert len(definitions) == 10
    assert {item["function"]["name"] for item in definitions} >= {"generate_campaign_plan", "forecast_gmv"}
    assert all(item["function"]["parameters"]["additionalProperties"] is False for item in definitions)


def test_parse_function_calls_accepts_structured_arguments():
    steps = parse_function_calls([{"id": "call-1", "function": {"name": "generate_campaign_plan", "arguments": '{"goal":"新品冷启动"}'}}])
    assert steps[0].tool_name == "generate_campaign_plan"
    assert steps[0].input["goal"] == "新品冷启动"


@pytest.mark.parametrize("raw", [
    [{"id": "call-1", "function": {"name": "drop_database", "arguments": "{}"}}],
    [{"id": "same", "function": {"name": "forecast_gmv", "arguments": "{}"}}, {"id": "same", "function": {"name": "forecast_gmv", "arguments": "{}"}}],
    [{"id": str(i), "function": {"name": "forecast_gmv", "arguments": "{}"}} for i in range(7)],
])
def test_parse_function_calls_rejects_unsafe_or_invalid_calls(raw):
    with pytest.raises(ValueError):
        parse_function_calls(raw)
