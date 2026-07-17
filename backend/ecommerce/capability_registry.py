from dataclasses import dataclass
from typing import Any


class CapabilityDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ToolCapability:
    name: str
    side_effect: str
    allowed_agents: frozenset[str]
    allowed_modes: frozenset[str]
    approval_action: str | None = None


class OperationsCapabilityRegistry:
    def __init__(self, capabilities: list[ToolCapability]):
        self.capabilities = {item.name: item for item in capabilities}

    @classmethod
    def default(cls):
        read_agents = frozenset({"Product Analyst", "Competitor Analyst", "Content Strategist", "Outcome Evaluator", "Supervisor"})
        return cls([
            ToolCapability("product_snapshot", "read_only", read_agents, frozenset({"read"})),
            ToolCapability("competitor_snapshot", "read_only", read_agents, frozenset({"read"})),
            ToolCapability("generate_variants", "read_only", frozenset({"Content Strategist"}), frozenset({"read"})),
            ToolCapability("generate_revised_variants", "read_only", frozenset({"Content Strategist"}), frozenset({"read"})),
            ToolCapability("run_sandbox_experiment", "sandbox_only", frozenset({"Experiment Executor"}), frozenset({"sandbox"})),
            ToolCapability("evaluate_kpi", "read_only", frozenset({"Outcome Evaluator"}), frozenset({"read"})),
            ToolCapability("write_product_price", "business_write", frozenset({"Tool Executor"}), frozenset({"write"}), "price_update"),
            ToolCapability("write_listing_status", "business_write", frozenset({"Tool Executor"}), frozenset({"write"}), "listing_update"),
            ToolCapability("create_campaign", "business_write", frozenset({"Tool Executor"}), frozenset({"write"}), "marketing_plan"),
        ])

    def authorize(self, agent: str, tool_name: str, *, mode: str, approval_scope: dict[str, Any] | None = None) -> ToolCapability:
        capability = self.capabilities.get(tool_name)
        if capability is None:
            raise CapabilityDenied(f"unknown tool capability: {tool_name}")
        if agent not in capability.allowed_agents or mode not in capability.allowed_modes:
            raise CapabilityDenied(f"agent {agent} is not allowed to use {tool_name} in {mode} mode")
        if capability.side_effect == "business_write":
            actions = approval_scope.get("actions", []) if approval_scope else []
            if not approval_scope or capability.approval_action not in actions:
                raise CapabilityDenied(f"tool {tool_name} requires a matching approval scope")
        return capability
