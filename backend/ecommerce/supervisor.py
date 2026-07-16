import json
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.config import settings
from backend.ecommerce.schemas import EcommerceDataset


class ExecutionPlan(BaseModel):
    action_type: Literal["price_update", "product_publish", "product_unpublish", "marketing_plan", "content_generation"]
    product_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class MarketingCopy(BaseModel):
    headline: str
    body: str
    selling_points: list[str] = Field(min_length=3, max_length=5)
    cta: str
    channel: str
    hashtags: list[str] = Field(default_factory=list, max_length=5)


class StructuredSupervisor:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    async def plan(self, goal: str, context: list[dict] | None = None) -> ExecutionPlan | None:
        if not settings.DEEPSEEK_API_KEY:
            return None
        products = [{"product_id": item.product_id, "name": item.name} for item in self.dataset.products]
        client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", timeout=15, max_retries=1)
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are an ecommerce execution supervisor. Return JSON only. Allowed actions: price_update, product_publish, product_unpublish, marketing_plan, content_generation. Use content_generation when the user asks for copywriting, titles, selling points, social posts, or ad copy. Never invent a product id. price_update parameters require new_price. marketing_plan parameters require goal. content_generation parameters may include channel and tone."},
                {"role": "user", "content": json.dumps({"goal": goal, "products": products, "recent_tasks": context or []}, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        action = payload.get("action_type") or payload.get("action")
        if any(word in goal for word in ("文案", "标题", "卖点", "种草", "帖子", "广告语")):
            action = "content_generation"
        product_id = payload.get("product_id")
        if not product_id:
            matches = [item.product_id for item in self.dataset.products if item.product_id.lower() in goal.lower() or item.name.lower() in goal.lower()]
            product_id = matches[0] if len(matches) == 1 else ""
        plan = ExecutionPlan.model_validate({
            "action_type": action,
            "product_id": product_id,
            "parameters": payload.get("parameters", {}),
            "confidence": payload.get("confidence", 0.8),
            "reasoning": payload.get("reasoning", "normalized provider response"),
        })
        if plan.product_id not in {item.product_id for item in self.dataset.products}:
            raise ValueError("LLM returned an unknown product")
        return plan

    async def generate_copy(self, goal: str, product: dict[str, Any]) -> dict[str, Any]:
        if not settings.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", timeout=30, max_retries=1)
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a senior Chinese ecommerce copywriter. Return JSON only with headline, body, selling_points (3-5 strings), cta, channel and hashtags. Do not invent discounts, certifications, efficacy or product specifications. Use only the supplied facts."},
                {"role": "user", "content": json.dumps({"request": goal, "product": {"name": product["name"], "category": product["category"], "price": product["price"], "positioning": product["positioning"]}}, ensure_ascii=False)},
            ],
        )
        copy = MarketingCopy.model_validate_json(response.choices[0].message.content or "{}").model_dump()
        return {**copy, "generation_mode": "llm", "model": settings.LLM_MODEL}
