import json
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.config import settings
from backend.ecommerce.schemas import EcommerceDataset


class ExecutionPlan(BaseModel):
    action_type: Literal["price_update", "product_publish", "product_unpublish", "marketing_plan"]
    product_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class StructuredSupervisor:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    async def plan(self, goal: str) -> ExecutionPlan | None:
        if not settings.DEEPSEEK_API_KEY:
            return None
        products = [{"product_id": item.product_id, "name": item.name} for item in self.dataset.products]
        client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", timeout=15, max_retries=1)
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are an ecommerce execution supervisor. Return JSON only. Allowed actions: price_update, product_publish, product_unpublish, marketing_plan. Never invent a product id. price_update parameters require new_price. marketing_plan parameters require goal."},
                {"role": "user", "content": json.dumps({"goal": goal, "products": products}, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        plan = ExecutionPlan.model_validate_json(content)
        if plan.product_id not in {item.product_id for item in self.dataset.products}:
            raise ValueError("LLM returned an unknown product")
        return plan
