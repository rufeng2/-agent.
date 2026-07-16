from collections.abc import Callable

from langgraph.graph import END, StateGraph

from backend.ecommerce.hybrid_agent import HybridEcommerceAgent
from backend.ecommerce.llm import Planner
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
        builder.add_node("execute_agent", self._execute_agent)
        builder.add_node("cancelled", self._cancelled)
        builder.add_node("complete", self._complete)
        builder.set_entry_point("load_context")
        builder.add_conditional_edges("load_context", lambda state: "cancelled" if state.get("status") == "cancelling" else "execute_agent", {"cancelled": "cancelled", "execute_agent": "execute_agent"})
        builder.add_conditional_edges("execute_agent", lambda state: "cancelled" if state.get("status") == "cancelling" else "complete", {"cancelled": "cancelled", "complete": "complete"})
        builder.add_edge("cancelled", END)
        builder.add_edge("complete", END)
        return builder.compile()

    async def run(self, question: str, context: list[dict], user_id: str = "demo-user", workspace_id: str = "default", session_id: str = "", run_id: str = "") -> EcommerceAgentState:
        return await self.graph.ainvoke({
            "question": question, "context": context, "user_id": user_id,
            "workspace_id": workspace_id, "session_id": session_id, "run_id": run_id,
            "status": "created", "node_trace": [], "warnings": [], "analysis": None,
        })

    async def _load_context(self, state: EcommerceAgentState):
        trace = [*state.get("node_trace", []), "load_context"]
        return {"node_trace": trace, "status": "cancelling" if self.is_cancelled() else "running"}

    async def _execute_agent(self, state: EcommerceAgentState):
        if self.is_cancelled():
            return {"status": "cancelling"}
        analysis = await HybridEcommerceAgent(self.dataset, planner=self.planner).analyze(
            state["question"], session_id=state.get("session_id", ""),
            user_id=state.get("user_id", "demo-user"), context=state.get("context", []),
        )
        return {"analysis": analysis.model_dump(), "node_trace": [*state.get("node_trace", []), "execute_agent"], "status": "running"}

    async def _cancelled(self, state: EcommerceAgentState):
        return {"status": "cancelled", "analysis": None, "node_trace": [*state.get("node_trace", []), "cancelled"]}

    async def _complete(self, state: EcommerceAgentState):
        return {"status": "completed", "node_trace": [*state.get("node_trace", []), "complete"]}
