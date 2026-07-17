from datetime import datetime, timezone
from typing import Any


class OperationTrace:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: list[dict[str, Any]] = []

    def emit(self, event: str, *, iteration: int = 0, step: str = "", agent: str = "", payload: dict[str, Any] | None = None) -> None:
        self.events.append({"ts": datetime.now(timezone.utc).isoformat(), "event": event, "run_id": self.run_id, "iteration": iteration, "step": step, "agent": agent, "payload": payload or {}})

    def stats(self) -> dict[str, Any]:
        return {"events": len(self.events), "steps": sum(1 for item in self.events if item["event"] == "step_completed"), "errors": sum(1 for item in self.events if item["event"] == "error"), "replans": sum(1 for item in self.events if item["event"] == "reflection" and item["payload"].get("decision") == "replan")}
