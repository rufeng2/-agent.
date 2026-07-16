from pathlib import Path

import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.growth_workflow import GrowthWorkflowService


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load_cached()


def test_growth_workflow_builds_research_listing_compliance_and_dag():
    result = GrowthWorkflowService(_dataset()).generate("P001", "Amazon US", "outdoor sunscreen")

    assert result["market_research"]["opportunity_score"] > 0
    assert len(result["listing"]["bullet_points"]) == 5
    assert result["compliance"]["status"] == "passed"
    assert [node["agent"] for node in result["dag"]] == [
        "market_research", "listing_writer", "compliance_reviewer", "human_approval", "sandbox_publisher"
    ]


def test_compliance_agent_blocks_absolute_claims():
    service = GrowthWorkflowService(_dataset())

    result = service.review_compliance({"title": "The best guaranteed cure", "bullet_points": [], "search_terms": []})

    assert result["status"] == "blocked"
    assert {item["rule"] for item in result["issues"]} == {"absolute_claim", "medical_claim"}


def test_publish_requires_approved_recommendation():
    service = GrowthWorkflowService(_dataset())
    workflow = service.generate("P001", "Amazon US", "outdoor")

    with pytest.raises(PermissionError, match="approval"):
        service.publish(workflow, recommendation_status="pending", recommendation_id="rec-1")


def test_approved_publish_returns_deterministic_sandbox_receipt():
    service = GrowthWorkflowService(_dataset())
    workflow = service.generate("P001", "Amazon US", "outdoor")

    first = service.publish(workflow, "approved", "rec-1")
    second = service.publish(workflow, "approved", "rec-1")

    assert first == second
    assert first["environment"] == "sandbox"
    assert first["status"] == "published"
