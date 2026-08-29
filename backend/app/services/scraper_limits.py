"""Per-domain rate limiting for job scrapers."""

import asyncio
import time

from app.config import settings

_locks: dict[str, asyncio.Lock] = {}
_last_request: dict[str, float] = {}


def _lock(domain: str) -> asyncio.Lock:
    if domain not in _locks:
        _locks[domain] = asyncio.Lock()
    return _locks[domain]


async def wait(domain: str) -> None:
    """Enforce minimum delay between requests to the same domain."""
    delay = settings.scraper_min_delay_ms / 1000.0
    async with _lock(domain):
        now = time.monotonic()
        last = _last_request.get(domain, 0.0)
        gap = now - last
        if gap < delay:
            await asyncio.sleep(delay - gap)
        _last_request[domain] = time.monotonic()
