import asyncio
import time

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.hybrid_agent import HybridEcommerceAgent


def test_deterministic_agent_analysis_stays_below_local_latency_budget():
    agent = HybridEcommerceAgent(EcommerceDataLoader().load_cached(), planner=None)
    asyncio.run(agent.analyze("warmup"))

    started = time.perf_counter()
    for _ in range(10):
        asyncio.run(agent.analyze("昨天 GMV 为什么下降？"))
    average_ms = (time.perf_counter() - started) * 1000 / 10

    assert average_ms < 100
