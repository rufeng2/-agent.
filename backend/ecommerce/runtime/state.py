from typing import TypedDict


class EcommerceAgentState(TypedDict, total=False):
    question: str
    context: list[dict]
    user_id: str
    workspace_id: str
    session_id: str
    run_id: str
    status: str
    node_trace: list[str]
    analysis: dict | None
    warnings: list[str]
    error: str
