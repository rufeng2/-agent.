"""Stage-level latency and outcome metrics for ecommerce Agent workflows."""
from contextlib import contextmanager
import time

from prometheus_client import Counter, Histogram


RAG_STAGE_DURATION = Histogram(
    "ecommerce_stage_duration_seconds",
    "Latency of individual ecommerce Agent workflow stages",
    ["stage", "status"],
)
CACHE_EVENTS = Counter("ecommerce_cache_events_total", "Ecommerce Agent cache outcomes", ["cache", "outcome"])
REFLECTION_EVENTS = Counter("ecommerce_reflection_events_total", "Ecommerce Agent reflection outcomes", ["outcome"])
SAFETY_EVENTS = Counter("ecommerce_safety_events_total", "Ecommerce Agent safety guard outcomes", ["stage", "outcome"])
RAG_TTFT = Histogram("ecommerce_ttft_seconds", "Time to first answer token", ["path"])
DEPENDENCY_DEGRADATION = Counter("ecommerce_dependency_degradation_total", "Dependency degradation decisions", ["dependency", "capability"])


class StageTimings:
    def __init__(self):
        self.started = time.perf_counter()
        self.values: dict[str, float] = {}
        self._ttft_recorded = False

    @contextmanager
    def track(self, stage: str):
        started = time.perf_counter()
        status = "ok"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            elapsed = time.perf_counter() - started
            self.values[stage] = round(self.values.get(stage, 0.0) + elapsed, 4)
            RAG_STAGE_DURATION.labels(stage=stage, status=status).observe(elapsed)

    def finish(self) -> dict[str, float]:
        self.values["total"] = round(time.perf_counter() - self.started, 4)
        return dict(self.values)

    def record(self, stage: str, elapsed: float, status: str = "ok") -> None:
        self.values[stage] = round(self.values.get(stage, 0.0) + elapsed, 4)
        RAG_STAGE_DURATION.labels(stage=stage, status=status).observe(elapsed)

    def record_ttft(self, path: str = "ecommerce_agent") -> float:
        elapsed = time.perf_counter() - self.started
        if not self._ttft_recorded:
            self._ttft_recorded = True
            self.values["ttft"] = round(elapsed, 4)
            RAG_TTFT.labels(path=path).observe(elapsed)
        return elapsed
