import json

from fastapi.testclient import TestClient

from backend.main import app


def _events(body: str):
    result = []
    current = {}
    for line in body.splitlines():
        if line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = json.loads(line[6:])
        elif not line and current:
            result.append(current)
            current = {}
    if current:
        result.append(current)
    return result


def test_agent_stream_emits_ordered_execution_events():
    with TestClient(app) as client:
        response = client.post("/api/ecommerce/agent/stream", json={"question": "昨天 GMV 为什么下降？"})

    events = _events(response.text)
    names = [item["event"] for item in events]
    assert response.status_code == 200
    assert names[0] == "planning"
    assert "tool_start" in names
    assert "tool_complete" in names
    assert names[-2:] == ["summarizing", "completed"]
    assert events[-1]["data"]["execution_mode"] == "deterministic_fallback"
    assert any(item["event"] == "warning" for item in events)
