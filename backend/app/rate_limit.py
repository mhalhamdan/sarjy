import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Sliding-window limiter kept in process memory.

    Counts reset when the process restarts, and are not shared between processes. That suits a
    single-container deployment; the OpenAI project budget cap is the hard stop on spend.
    """

    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        """Record an attempt for `key`. Returns False when the limit is already reached."""
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
