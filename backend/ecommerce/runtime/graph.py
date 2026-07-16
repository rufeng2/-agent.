from collections.abc import Callable

from langgraph.graph import END, StateGraph

from backend.ecommerce.llm import Planner
from backend.ecommerce.multi_agent import MultiAgentCoordinator, TEAM_ROLES
from backend.ecommerce.runtime.state import EcommerceAgentState
from backend.ecommerce.schemas import EcommerceDataset


class EcommerceGraphRuntime:
    def __init__(self, dataset: EcommerceDataset, planner: Planner | None = None, is_cancelled: Callable[[], bool] | None = None):
        self.dataset = dataset
        self.planner = planner
        self.is_cancelled = is_cancelled or (lambda: False)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(EcommerceAgentState)
        builder.add_node("load_context", self._load_context)
        builder.add_node("supervisor", self._supervisor)
        for role in ("product_research", "pricing", "listing", "advertising", "customer_service"):
            builder.add_node(role, self._specialist_node(role))
        builder.add_node("supervisor_summary", self._supervisor_summary)
        builder.add_node("cancelled", self._cancelled)
        builder.add_node("complete", self._complete)
        builder.set_entry_point("load_context")
        builder.add_conditional_edges("load_context", lambda state: "cancelled" if state.get("status") == "cancelling" else "supervisor", {"cancelled": "cancelled", "supervisor": "supervisor"})
        builder.add_edge("supervisor", "product_research")
        builder.add_edge("product_research", "pricing")
        builder.add_edge("pricing", "listing")
        builder.add_edge("listing", "advertising")
        builder.add_edge("advertising", "customer_service")
        builder.add_edge("customer_service", "supervisor_summary")
        builder.add_edge("supervisor_summary", "complete")
        builder.add_edge("cancelled", END)
        builder.add_edge("complete", END)
        return builder.compile()

    async def run(self, question: str, context: list[dict], user_id: str = "demo-user", workspace_id: str = "default", session_id: str = "", run_id: str = "", agent_memories: dict[str, dict] | None = None) -> EcommerceAgentState:
        return await self.graph.ainvoke({
            "question": question, "context": context, "user_id": user_id,
            "workspace_id": workspace_id, "session_id": session_id, "run_id": run_id,
            "status": "created", "node_trace": [], "warnings": [], "analysis": None,
            "selected_agents": [], "specialist_reports": [], "risk_review": {},
            "planner_used": False, "planner_fallback": "",
            "agent_memories": agent_memories or {},
        })

    async def _load_context(self, state: EcommerceAgentState):
        trace = [*state.get("node_trace", []), "load_context"]
        return {"node_trace": trace, "status": "cancelling" if self.is_cancelled() else "running"}

    async def _supervisor(self, state: EcommerceAgentState):
        selected = None
        fallback = ""
        if self.planner is not None and hasattr(self.planner, "route_team"):
            try:
                candidate = await self.planner.route_team(state["question"], state.get("context", []))
                if candidate and all(role in TEAM_ROLES for role in candidate):
                    selected = list(dict.fromkeys(candidate))
                else:
                    fallback = "invalid_team_route"
            except Exception:
                fallback = "team_llm_unavailable"
        if selected is None:
            selected = MultiAgentCoordinator(self.dataset).route(state["question"])
        return {"selected_agents": selected, "planner_used": not fallback and self.planner is not None, "planner_fallback": fallback, "node_trace": [*state.get("node_trace", []), "supervisor"]}

    def _specialist_node(self, role: str):
        async def execute(state: EcommerceAgentState):
            trace = [*state.get("node_trace", []), role]
            if role not in state.get("selected_agents", []):
                return {"node_trace": trace}
            report = MultiAgentCoordinator(self.dataset).run_specialist(role, state["question"], state.get("agent_memories", {}).get(role, {}))
            return {"specialist_reports": [*state.get("specialist_reports", []), report], "node_trace": trace}
        return execute

    async def _supervisor_summary(self, state: EcommerceAgentState):
        coordinator = MultiAgentCoordinator(self.dataset)
        review = coordinator.review(state.get("specialist_reports", []))
        analysis = coordinator.synthesize(state["question"], state.get("specialist_reports", []), review)
        if state.get("planner_used") and self.planner is not None and hasattr(self.planner, "summarize_team"):
            try:
                analysis.summary = await self.planner.summarize_team(state["question"], analysis.team_deliverables)
                analysis.execution_mode = "openclaw_team_llm"
                analysis.prompt_tokens = int(getattr(self.planner, "prompt_tokens", 0))
                analysis.completion_tokens = int(getattr(self.planner, "completion_tokens", 0))
            except Exception:
                analysis.fallback_reason = "team_summary_unavailable"
        elif state.get("planner_fallback"):
            analysis.fallback_reason = state["planner_fallback"]
        analysis.session_id = state.get("session_id", "")
        analysis.run_id = state.get("run_id", "") or analysis.run_id
        return {"analysis": analysis.model_dump(), "risk_review": review, "node_trace": [*state.get("node_trace", []), "supervisor_summary"]}

    async def _cancelled(self, state: EcommerceAgentState):
        return {"status": "cancelled", "analysis": None, "node_trace": [*state.get("node_trace", []), "cancelled"]}

    async def _complete(self, state: EcommerceAgentState):
        return {"status": "completed", "node_trace": [*state.get("node_trace", []), "complete"]}
