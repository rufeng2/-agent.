from uuid import NAMESPACE_URL, uuid5

from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.tools import EcommerceTools


class CommerceActionAgent:
    def __init__(self, dataset: EcommerceDataset, repository: EcommerceRepository | None = None):
        self.dataset = dataset
        self.repository = repository

    def propose(self, action_type: str, product_id: str, parameters: dict) -> dict:
        product = next((item for item in self.dataset.products if item.product_id == product_id), None)
        if product is None:
            raise KeyError(product_id)
        payload = {"action_type": action_type, "product_id": product_id}
        if action_type == "price_update":
            new_price = float(parameters.get("new_price", 0))
            change_pct = (new_price - product.price) / product.price * 100
            if abs(change_pct) > 20:
                raise ValueError("Price change cannot exceed 20% in one action")
            if new_price <= product.cost:
                raise ValueError("New price must remain above product cost")
            payload.update({"old_price": product.price, "new_price": round(new_price, 2), "change_pct": round(change_pct, 2)})
            return _proposal(f"将 {product.name} 价格调整为 {new_price:.2f} 元", action_type, "high", f"当前价格 {product.price} 元，拟调整 {change_pct:.2f}%", "更新商品售价并重新计算价格竞争力", payload)
        if action_type in {"product_publish", "product_unpublish"}:
            target = "listed" if action_type == "product_publish" else "unlisted"
            payload["listing_status"] = target
            verb = "上架" if target == "listed" else "下架"
            return _proposal(f"{verb}商品 {product.name}", action_type, "high", f"运营人员请求执行商品{verb}", f"商品状态更新为 {target}", payload)
        if action_type == "marketing_plan":
            goal = str(parameters.get("goal", "大促增长"))
            plan, _trace = EcommerceTools(self.dataset).generate_campaign_plan(goal)
            payload.update({"goal": goal, "plan": plan})
            return _proposal(f"创建 {goal} 营销计划", action_type, "medium", f"围绕 {product.name} 制定可执行营销方案", "创建营销计划和选品策略，等待运营确认", payload)
        raise ValueError(f"Unsupported action type: {action_type}")

    async def execute(self, recommendation_id: str) -> dict:
        if self.repository is None:
            raise RuntimeError("Repository is required for execution")
        existing = await self.repository.get_action_execution(recommendation_id)
        if existing:
            return existing.receipt
        recommendation = await self.repository.get_recommendation(recommendation_id)
        if recommendation is None:
            raise KeyError(recommendation_id)
        if recommendation.status != "approved":
            raise PermissionError("Human approval is required before execution")
        payload = next((item["action_payload"] for item in recommendation.evidence if "action_payload" in item), None)
        if payload is None:
            raise ValueError("Recommendation has no executable action payload")
        action_type = payload["action_type"]
        if action_type == "price_update":
            await self.repository.apply_catalog_action(payload["product_id"], price_override=float(payload["new_price"]))
        elif action_type in {"product_publish", "product_unpublish"}:
            await self.repository.apply_catalog_action(payload["product_id"], listing_status=payload["listing_status"])
        elif action_type != "marketing_plan":
            raise ValueError(f"Unsupported action type: {action_type}")
        receipt_id = str(uuid5(NAMESPACE_URL, f"commerce-action:{recommendation_id}"))
        receipt = {"receipt_id": receipt_id, "recommendation_id": recommendation_id, "action_type": action_type, "status": "completed", "environment": "sandbox", "payload": payload}
        await self.repository.create_action_execution(recommendation_id, action_type, payload, receipt)
        return receipt


def _proposal(title: str, action_type: str, risk_level: str, reason: str, impact: str, payload: dict) -> dict:
    return {"title": title, "action_type": action_type, "risk_level": risk_level, "reason": reason, "expected_impact": impact, "payload": payload}
