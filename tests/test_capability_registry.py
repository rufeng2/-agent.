import pytest

from backend.ecommerce.capability_registry import CapabilityDenied, OperationsCapabilityRegistry


def test_read_only_agent_cannot_receive_mutating_tool():
    registry = OperationsCapabilityRegistry.default()
    with pytest.raises(CapabilityDenied, match="write_product_price"):
        registry.authorize("Competitor Analyst", "write_product_price", mode="read")


def test_executor_requires_approval_scope_for_business_write():
    registry = OperationsCapabilityRegistry.default()
    with pytest.raises(CapabilityDenied, match="approval scope"):
        registry.authorize("Tool Executor", "write_product_price", mode="write", approval_scope=None)

    capability = registry.authorize("Tool Executor", "write_product_price", mode="write", approval_scope={"product_id": "P003", "actions": ["price_update"]})
    assert capability.side_effect == "business_write"


def test_sandbox_experiment_is_allowed_without_business_approval():
    registry = OperationsCapabilityRegistry.default()
    capability = registry.authorize("Experiment Executor", "run_sandbox_experiment", mode="sandbox")
    assert capability.side_effect == "sandbox_only"
