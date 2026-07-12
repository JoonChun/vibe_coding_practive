import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import db
import pipeline
from config import SNAPSHOT_CACHE_TTL_SECONDS, TIMEZONE

_CACHE = {"items": None, "cached_at": None}
_LOCK = asyncio.Lock()


def _to_snapshot_item(item: dict) -> dict:
    return {
        "code": item.get("code"),
        "name": item.get("name"),
        "close": item.get("close"),
        "short_view": item.get("short_view"),
        "long_view": item.get("long_view"),
        "source": item.get("source"),
        "error": item.get("error"),
    }


def _recompute() -> dict:
    stock_list = db.load_watchlist()
    success, failed = pipeline.collect_snapshots(stock_list)
    items = [_to_snapshot_item(item) for item in success + failed]

    now = datetime.now(ZoneInfo(TIMEZONE))
    _CACHE["items"] = items
    _CACHE["cached_at"] = now

    return {
        "generated_at": now.isoformat(),
        "cache_hit": False,
        "items": items,
    }


def _cached_response(cached_at: datetime) -> dict:
    return {
        "generated_at": cached_at.isoformat(),
        "cache_hit": True,
        "items": _CACHE["items"],
    }


async def get_snapshot() -> dict:
    now = datetime.now(ZoneInfo(TIMEZONE))
    cached_at = _CACHE.get("cached_at")
    if cached_at is not None and (now - cached_at).total_seconds() < SNAPSHOT_CACHE_TTL_SECONDS:
        return _cached_response(cached_at)

    async with _LOCK:
        now = datetime.now(ZoneInfo(TIMEZONE))
        cached_at = _CACHE.get("cached_at")
        if cached_at is not None and (now - cached_at).total_seconds() < SNAPSHOT_CACHE_TTL_SECONDS:
            return _cached_response(cached_at)
        return await asyncio.to_thread(_recompute)
