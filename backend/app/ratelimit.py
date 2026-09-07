"""In-memory abuse guard, ported unchanged from the legacy backend/app.py.

Single-instance, no cross-replica coordination — an accepted trade-off for a
one-person portfolio service, not an oversight. If this ever runs with more
than one replica, move counters to something shared (e.g. Redis) instead of
raising the limits to compensate.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import Settings


class RateLimiter:
    def __init__(self, settings: Settings):
        self.per_minute = settings.rate_limit_per_min
        self.per_day = settings.rate_limit_per_day
        self.global_per_day = settings.rate_limit_global_per_day
        self._minute_hits: dict[str, deque] = defaultdict(deque)
        self._day_hits: dict[str, deque] = defaultdict(deque)
        self._global_day_hits: deque = deque()

    @staticmethod
    def client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _prune(dq: deque, window: float, now: float) -> None:
        while dq and now - dq[0] > window:
            dq.popleft()

    def check(self, request: Request) -> None:
        now = time.monotonic()
        ip = self.client_ip(request)

        self._prune(self._global_day_hits, 86400, now)
        if len(self._global_day_hits) >= self.global_per_day:
            raise HTTPException(429, "Chappie is at capacity for today. Try again tomorrow, or email him directly.")

        minute_dq = self._minute_hits[ip]
        self._prune(minute_dq, 60, now)
        if len(minute_dq) >= self.per_minute:
            raise HTTPException(429, "Too many questions in a row. Wait a minute and try again.")

        day_dq = self._day_hits[ip]
        self._prune(day_dq, 86400, now)
        if len(day_dq) >= self.per_day:
            raise HTTPException(429, "Daily question limit reached for this visitor. Try again tomorrow.")

        minute_dq.append(now)
        day_dq.append(now)
        self._global_day_hits.append(now)
