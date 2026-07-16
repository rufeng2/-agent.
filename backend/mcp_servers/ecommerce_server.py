import os
from uuid import NAMESPACE_URL, uuid5

from mcp.server.fastmcp import FastMCP

from backend.config import settings
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.persistence.repository import VersionConflict
from backend.ecommerce.tool_response import ToolResponse


mcp = FastMCP(
    "ecommerce-operations",
    instructions="Controlled ecommerce catalog and marketing tools. Mutating tools require an approved task id.",
    log_level="ERROR",
)


def _database_url() -> str:
    return os.getenv("MCP_ECOMMERCE_DATABASE_URL", settings.ECOMMERCE_DATABASE_URL)


async def _product_snapshot(product_id: str) -> dict:
    dataset = EcommerceDataLoader().load_cached()
    product = next((item for item in dataset.products if item.product_id == product_id), None)
    if product is None:
        raise ValueError("product not found")
    repository = EcommerceRepository(_database_url())
    await repository.initialize()
    try:
        state = {item.product_id: item for item in await repository.list_catalog_states()}.get(product_id)
        data = product.model_dump(mode="json")
        data.update({
            "price": state.price_override if state and state.price_override is not None else product.price,
            "listing_status": state.listing_status if state else "listed",
            "catalog_version": state.version if state else 1,
        })
        return data
    finally:
        await repository.dispose()


async def _require_approval(approved_task_id: str, action_type: str, product_id: str, parameters: dict) -> dict:
    if not approved_task_id.strip():
        raise ValueError("approved_task_id is required for mutating tools")
    repository = EcommerceRepository(_database_url())
    await repository.initialize()
    try:
        task = await repository.get_execution_task_by_id(approved_task_id)
    finally:
        await repository.dispose()
    if task is None:
        raise PermissionError("approved task does not exist")
    if task.status not in {"running", "rolling_back"} or not task.state.get("approved"):
        raise PermissionError("task is not in an approved running state")
    approval = task.state.get("approval", {})
    approved_action = approval.get("action_type")
    action_allowed = approved_action == action_type or (approved_action == "composite" and action_type in {"price_update", "marketing_plan", "rollback"})
    if not action_allowed or approval.get("product_id") != product_id:
        raise PermissionError("tool call does not match the approved action")
    approved_parameters = approval.get("parameters", {})
    def matches(approved, requested) -> bool:
        if isinstance(requested, dict):
            return isinstance(approved, dict) and all(key in approved and matches(approved[key], value) for key, value in requested.items())
        return approved == requested
    for key, value in parameters.items():
        if key not in approved_parameters or not matches(approved_parameters[key], value):
            raise PermissionError(f"parameter {key} does not match the approved snapshot")
    return {"workspace_id": task.workspace_id, "operator": approval.get("operator", "")}


@mcp.tool()
async def get_product(product_id: str) -> dict:
    """Get the current product, price, listing status and optimistic-lock version."""
    try:
        return ToolResponse.success(await _product_snapshot(product_id), tool="get_product").model_dump(mode="json")
    except ValueError as exc:
        return ToolResponse.error("NOT_FOUND", str(exc)).model_dump(mode="json")


@mcp.tool()
async def update_product_price(product_id: str, new_price: float, expected_version: int, approved_task_id: str) -> dict:
    """Update a product price after approval and return before/after snapshots."""
    try:
        identity = await _require_approval(approved_task_id, "price_update", product_id, {"new_price": new_price})
        before = await _product_snapshot(product_id)
        if new_price <= float(before["cost"]):
            raise ValueError("new price must remain above cost")
        repository = EcommerceRepository(_database_url())
        await repository.initialize()
        try:
            await repository.apply_catalog_action(product_id, price_override=new_price, expected_version=expected_version)
        finally:
            await repository.dispose()
        data = {"before": before, "after": await _product_snapshot(product_id), "approved_task_id": approved_task_id, **identity}
        return ToolResponse.success(data, tool="update_product_price").model_dump(mode="json")
    except PermissionError as exc:
        return ToolResponse.error("APPROVAL_DENIED", str(exc)).model_dump(mode="json")
    except VersionConflict as exc:
        return ToolResponse.error("VERSION_CONFLICT", str(exc), retryable=True).model_dump(mode="json")
    except ValueError as exc:
        return ToolResponse.error("INVALID_PARAM", str(exc)).model_dump(mode="json")


@mcp.tool()
async def set_product_listing(product_id: str, listing_status: str, expected_version: int, approved_task_id: str) -> dict:
    """Publish or unpublish a product after approval."""
    try:
        action_type = "product_publish" if listing_status == "listed" else "product_unpublish"
        identity = await _require_approval(approved_task_id, action_type, product_id, {"listing_status": listing_status})
        if listing_status not in {"listed", "unlisted"}:
            raise ValueError("listing_status must be listed or unlisted")
        before = await _product_snapshot(product_id)
        repository = EcommerceRepository(_database_url())
        await repository.initialize()
        try:
            await repository.apply_catalog_action(product_id, listing_status=listing_status, expected_version=expected_version)
        finally:
            await repository.dispose()
        data = {"before": before, "after": await _product_snapshot(product_id), "approved_task_id": approved_task_id, **identity}
        return ToolResponse.success(data, tool="set_product_listing").model_dump(mode="json")
    except PermissionError as exc:
        return ToolResponse.error("APPROVAL_DENIED", str(exc)).model_dump(mode="json")
    except VersionConflict as exc:
        return ToolResponse.error("VERSION_CONFLICT", str(exc), retryable=True).model_dump(mode="json")
    except ValueError as exc:
        return ToolResponse.error("INVALID_PARAM", str(exc)).model_dump(mode="json")


@mcp.tool()
async def rollback_product(product_id: str, price: float | None, listing_status: str | None, expected_version: int, approved_task_id: str) -> dict:
    """Restore a prior catalog snapshot after an approved rollback."""
    try:
        identity = await _require_approval(approved_task_id, "rollback", product_id, {})
        before = await _product_snapshot(product_id)
        repository = EcommerceRepository(_database_url())
        await repository.initialize()
        try:
            await repository.apply_catalog_action(product_id, price_override=price, listing_status=listing_status, expected_version=expected_version)
        finally:
            await repository.dispose()
        data = {"before": before, "after": await _product_snapshot(product_id), "approved_task_id": approved_task_id, **identity}
        return ToolResponse.success(data, tool="rollback_product").model_dump(mode="json")
    except PermissionError as exc:
        return ToolResponse.error("APPROVAL_DENIED", str(exc)).model_dump(mode="json")
    except VersionConflict as exc:
        return ToolResponse.error("VERSION_CONFLICT", str(exc), retryable=True).model_dump(mode="json")
    except ValueError as exc:
        return ToolResponse.error("INVALID_PARAM", str(exc)).model_dump(mode="json")


@mcp.tool()
async def create_marketing_campaign(product_id: str, name: str, daily_budget: float, target_acos_pct: float, approved_task_id: str) -> dict:
    """Create an approved sandbox marketing campaign receipt."""
    try:
        identity = await _require_approval(approved_task_id, "marketing_plan", product_id, {"campaign": {"name": name, "daily_budget": daily_budget, "target_acos_pct": target_acos_pct}})
        await _product_snapshot(product_id)
        if daily_budget <= 0 or target_acos_pct <= 0:
            raise ValueError("budget and target ACOS must be positive")
        repository = EcommerceRepository(_database_url())
        await repository.initialize()
        try:
            campaign = await repository.create_campaign(identity["workspace_id"], approved_task_id, product_id, name, daily_budget, target_acos_pct)
        finally:
            await repository.dispose()
        data = {"campaign_id": campaign.id, "product_id": product_id, "name": name, "daily_budget": daily_budget, "target_acos_pct": target_acos_pct, "status": campaign.status, "version": campaign.version, "environment": "sandbox", "approved_task_id": approved_task_id, **identity}
        return ToolResponse.success(data, tool="create_marketing_campaign").model_dump(mode="json")
    except PermissionError as exc:
        return ToolResponse.error("APPROVAL_DENIED", str(exc)).model_dump(mode="json")
    except ValueError as exc:
        return ToolResponse.error("INVALID_PARAM", str(exc)).model_dump(mode="json")


@mcp.tool()
async def get_marketing_campaign(campaign_id: str, workspace_id: str) -> dict:
    """Read a persisted marketing campaign."""
    repository = EcommerceRepository(_database_url())
    await repository.initialize()
    try:
        campaign = await repository.get_campaign(campaign_id, workspace_id)
    finally:
        await repository.dispose()
    if campaign is None:
        return ToolResponse.error("NOT_FOUND", "campaign not found").model_dump(mode="json")
    return ToolResponse.success({"campaign_id": campaign.id, "product_id": campaign.product_id, "name": campaign.name, "daily_budget": campaign.daily_budget, "target_acos_pct": campaign.target_acos_pct, "status": campaign.status, "version": campaign.version}).model_dump(mode="json")


if __name__ == "__main__":
    mcp.run(transport="stdio")
