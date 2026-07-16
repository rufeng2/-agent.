import asyncio
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.evaluation import EvaluationCase, evaluate_cases
from backend.ecommerce.hybrid_agent import HybridEcommerceAgent


async def main(online: bool = False) -> None:
    cases = [EvaluationCase.model_validate(item) for item in json.loads(Path("data/ecommerce/evaluation_cases.json").read_text(encoding="utf-8"))]
    agent = HybridEcommerceAgent(EcommerceDataLoader().load_cached(), use_configured_planner=online)

    async def analyze(case):
        return (await agent.analyze(case.question)).model_dump()

    report = await evaluate_cases(cases, analyze)
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true", help="Use the configured DeepSeek model")
    args = parser.parse_args()
    asyncio.run(main(online=args.online))
