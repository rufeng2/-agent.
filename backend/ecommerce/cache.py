import threading
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, ttl_seconds: float = 30, clock: Callable[[], float] = time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._values: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        now = self.clock()
        with self._lock:
            cached = self._values.get(key)
            if cached and cached[0] > now:
                return cached[1]  # type: ignore[return-value]
            value = factory()
            self._values[key] = (now + self.ttl_seconds, value)
            return value

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
