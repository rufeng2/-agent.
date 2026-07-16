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
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _record_usage(self, response) -> None:
        if response.usage:
            self.prompt_tokens += response.usage.prompt_tokens or 0
            self.completion_tokens += response.usage.completion_tokens or 0

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
        self._record_usage(response)
        return AgentPlan.model_validate(json.loads(response.choices[0].message.content or "{}"))

    async def summarize(self, question: str, results: list[dict]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model, temperature=0.2,
            messages=[
                {"role": "system", "content": "仅依据给定工具结果生成简洁中文经营结论，不编造数字。"},
                {"role": "user", "content": json.dumps({"question": question, "tool_results": results}, ensure_ascii=False)},
            ],
        )
        self._record_usage(response)
        return response.choices[0].message.content or "工具分析已完成。"


def configured_planner() -> DeepSeekPlanner | None:
    return DeepSeekPlanner(settings.DEEPSEEK_API_KEY, settings.LLM_MODEL) if settings.DEEPSEEK_API_KEY else None


class DeepSeekTeamPlanner:
    allowed_agents = ["product_research", "pricing", "listing", "advertising", "customer_service"]

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=settings.PROVIDER_TIMEOUT_SECONDS)
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _record_usage(self, response) -> None:
        if response.usage:
            self.prompt_tokens += response.usage.prompt_tokens or 0
            self.completion_tokens += response.usage.completion_tokens or 0

    async def route_team(self, question: str, context: list[dict]) -> list[str]:
        response = await self.client.chat.completions.create(
            model=self.model, response_format={"type": "json_object"}, temperature=0,
            messages=[
                {"role": "system", "content": "你是跨境电商团队主管。只返回 JSON {\"agents\":[...]}。可选角色仅为 product_research、pricing、listing、advertising、customer_service。按完成目标所需的最小团队选择；新品从0到上架必须选择全部五个角色。不得返回其他角色。"},
                *context[-6:], {"role": "user", "content": question},
            ],
        )
        self._record_usage(response)
        payload = json.loads(response.choices[0].message.content or "{}")
        agents = payload.get("agents")
        if not isinstance(agents, list):
            raise ValueError("agents must be a list")
        return [str(agent) for agent in agents]

    async def summarize_team(self, question: str, deliverables: dict[str, dict]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model, temperature=0.2,
            messages=[
                {"role": "system", "content": "你是跨境电商团队主管。仅依据专员交付物，用中文汇总：推荐结论、定价与利润、Listing、推广、客服准备、风险和下一步。不得编造数字，200字以内。"},
                {"role": "user", "content": json.dumps({"goal": question, "deliverables": deliverables}, ensure_ascii=False)},
            ],
        )
        self._record_usage(response)
        return response.choices[0].message.content or "团队交付物已汇总。"


def configured_team_planner() -> DeepSeekTeamPlanner | None:
    return DeepSeekTeamPlanner(settings.DEEPSEEK_API_KEY, settings.LLM_MODEL) if settings.DEEPSEEK_API_KEY else None
