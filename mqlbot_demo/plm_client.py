"""Mock PLM client with the same rate-limiting behavior as the production client."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Awaitable, Callable

DATA_DIR = Path(__file__).parent / "data"


class PLMError(Exception):
    """Raised when the PLM system cannot return data."""


class RateLimiter:
    """Limits concurrent calls and calls per rolling 60-second window.

    A single user lookup triggers several PLM calls (detail + history), so the
    limiter protects the upstream system from bursts. Clock and sleep are
    injectable to keep tests fast and deterministic.
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        max_per_minute: int = 20,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.max_per_minute = max_per_minute
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._clock = clock
        self._sleep = sleep
        self._calls: list[float] = []

    async def _wait_for_slot(self) -> None:
        while True:
            now = self._clock()
            self._calls = [t for t in self._calls if now - t < 60]
            if len(self._calls) < self.max_per_minute:
                self._calls.append(now)
                return
            await self._sleep(60 - (now - self._calls[0]) + 0.01)

    async def run(self, func: Callable[[], Awaitable]):
        async with self._semaphore:
            await self._wait_for_slot()
            return await func()


class MockPLMClient:
    """Serves issue details and history from a JSON file instead of the PLM API."""

    def __init__(self, data_file: Path | str = DATA_DIR / "plm_issues.json", limiter: RateLimiter | None = None):
        self._issues = json.loads(Path(data_file).read_text(encoding="utf-8"))
        self.limiter = limiter or RateLimiter()
        self.call_count = 0

    async def _call(self, func):
        async def wrapped():
            self.call_count += 1
            return func()
        return await self.limiter.run(wrapped)

    async def get_detail(self, issue_number: str) -> dict | None:
        def fetch():
            record = self._issues.get(issue_number)
            return dict(record["detail"]) if record else None
        return await self._call(fetch)

    async def get_history(self, issue_number: str) -> list[dict]:
        def fetch():
            record = self._issues.get(issue_number)
            if not record:
                return []
            if record["detail"].get("history_unavailable"):
                raise PLMError("History service timed out")
            return list(record.get("history", []))
        return await self._call(fetch)
