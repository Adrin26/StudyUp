"""In-process sliding-window rate limiter.

Adequate for a single API instance. Running several instances would need a
shared store (e.g. a Postgres table) so limits apply across them.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and hits[0] <= now - window:
            hits.popleft()
        return hits

    def blocked(self, key: str, limit: int, window_seconds: float) -> bool:
        with self._lock:
            return len(self._prune(key, window_seconds, time.monotonic())) >= limit

    def hit(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())

    def check_and_hit(self, key: str, limit: int, window_seconds: float) -> None:
        with self._lock:
            hits = self._prune(key, window_seconds, time.monotonic())
            if len(hits) >= limit:
                raise too_many()
            hits.append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


def too_many() -> HTTPException:
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Please wait a few minutes and try again.")


limiter = RateLimiter()
