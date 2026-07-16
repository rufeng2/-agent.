import pytest

from backend.ecommerce.mcp_client import EcommerceMCPClient


@pytest.mark.asyncio
async def test_mcp_server_supports_tool_discovery_and_read(tmp_path):
    client = EcommerceMCPClient(f"sqlite+aiosqlite:///{tmp_path / 'mcp.db'}")
    tools = await client.list_tools()
    product = await client.call_tool("get_product", {"product_id": "P002"})

    assert {item["name"] for item in tools} >= {"get_product", "update_product_price", "set_product_listing", "rollback_product", "create_marketing_campaign"}
    assert product["product_id"] == "P002"
    assert product["catalog_version"] == 1


@pytest.mark.asyncio
async def test_mcp_server_rejects_mutation_without_approved_task(tmp_path):
    client = EcommerceMCPClient(f"sqlite+aiosqlite:///{tmp_path / 'mcp.db'}")

    with pytest.raises(RuntimeError, match="approved_task_id"):
        await client.call_tool("update_product_price", {"product_id": "P002", "new_price": 300, "expected_version": 1, "approved_task_id": ""})
