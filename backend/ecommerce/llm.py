import json
from typing import Protocol

from openai import AsyncOpenAI

from backend.config import settings
from backend.ecommerce.planning import AgentPlan


class Planner(Protocol):
    async def plan(self, question: str, context: list[dict]) -> AgentPlan: ...
    async def summarize(self, question: str, results: list[dict]) -> str: ...


class DeepSeekPlanner:
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=settings.PROVIDER_TIMEOUT_SECONDS)

    async def plan(self, question: str, context: list[dict]) -> AgentPlan:
        response = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "你是电商运营规划器。只返回 JSON: intent, goal, steps；steps 每项包含 tool_name 和 input，最多6步。"},
                *context[-6:],
                {"role": "user", "content": question},
            ],
        )
        return AgentPlan.model_validate(json.loads(response.choices[0].message.content or "{}"))

    async def summarize(self, question: str, results: list[dict]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model, temperature=0.2,
            messages=[
                {"role": "system", "content": "仅依据给定工具结果生成简洁中文经营结论，不编造数字。"},
                {"role": "user", "content": json.dumps({"question": question, "tool_results": results}, ensure_ascii=False)},
            ],
        )
        return response.choices[0].message.content or "工具分析已完成。"


def configured_planner() -> DeepSeekPlanner | None:
    return DeepSeekPlanner(settings.DEEPSEEK_API_KEY, settings.LLM_MODEL) if settings.DEEPSEEK_API_KEY else None
