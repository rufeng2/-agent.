import json


async def analysis_events(analysis: dict):
    yield _event("planning", {"run_id": analysis.get("run_id", ""), "status": "completed"})
    if analysis.get("fallback_reason"):
        yield _event("warning", {"code": analysis["fallback_reason"], "message": "LLM 不可用，已使用确定性分析"})
    for warning in analysis.get("warnings", []):
        yield _event("warning", {"code": "tool_partial_failure", "message": warning})
    for index, step in enumerate(analysis.get("tool_trace", []), start=1):
        yield _event("tool_start", {"index": index, "tool_name": step["tool_name"], "input": step["input"]})
        yield _event("tool_complete", {"index": index, "tool_name": step["tool_name"], "summary": step["output_summary"]})
    yield _event("summarizing", {"status": "completed"})
    yield _event("completed", analysis)


def _event(name: str, data: dict) -> dict[str, str]:
    return {"event": name, "data": json.dumps(data, ensure_ascii=False)}
