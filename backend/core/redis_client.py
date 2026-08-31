# core/redis_client.py
"""Shared Redis client (docs/rbac-redis-plan.md) -- this codebase already has
SIX independent Redis-with-in-memory-fallback implementations (core/rate_limit.py,
core/session_store.py, core/chat_history.py, webhook/dispatch.py's _get_redis(),
modules/booking/calendar.py's _get_redis(), and now auth/refresh_tokens.py
makes it seven without this module), each hand-rolling the same
`redis.from_url(url); r.ping(); except Exception: fall back` connect dance.
main.py is NOT one of these -- its `perms:invalidate` pub/sub subscriber
imports get_redis() from THIS module directly, so it was never a separate
hand-rolled site to begin with. This module exists so THIS feature (and any
future cache/pub-sub/queue need) reaches for one shared thing instead of an
eighth bespoke implementation -- it deliberately does NOT migrate those six
existing call sites onto it (a separate, low-risk cleanup later, per the
plan's own Rollout section); they keep working exactly as they are.

REDIS_URL is read live via core/config.py's get_settings().REDIS_URL on
every get_redis() call -- NOT a module-level constant, and NOT the raw
os.environ.get() every other Redis call site in this codebase uses. This is
safe specifically because get_settings() builds a brand-new Settings()
instance (reading current process env) on every call rather than caching one
at import time (see core/config.py's own docstring) -- calling it fresh here,
inside the function, preserves the exact live-per-call re-read semantics
os.environ.get() would have given it, including still observing a test's
`monkeypatch.setenv/delenv("REDIS_URL", ...)`. The other six hand-rolled
Redis call sites (core/rate_limit.py, core/session_store.py,
core/chat_history.py, webhook/dispatch.py, modules/booking/calendar.py,
auth/refresh_tokens.py) are deliberately NOT changed to match -- this is
scoped to get_redis() alone.

get_redis() returns None (never raises) when Redis is unset or unreachable
-- every function below is a no-op / returns a default in that case, so a
caller never needs its own try/except around a Redis outage; that's the
whole point of routing every Redis touch through this one module."""
import json
from typing import Any, cast

import redis

from core.config import get_settings


def get_redis() -> "redis.Redis | None":
    """Same from_url + ping() + except: None gating as every existing
    RedisX/_build_x() factory in this codebase (core/rate_limit.py's
    _build_limiter(), core/session_store.py's get_session_store()) -- a fresh
    connection is opened per call rather than cached at module level,
    because ping() itself is the liveness check callers rely on to decide
    whether to even attempt the Redis path this request; a cached client
    that silently stopped working would defeat that. redis-py pools
    connections internally per client instance regardless, so this is not
    the "new TCP connection per call" cost it might look like."""
    redis_url = get_settings().REDIS_URL
    if not redis_url:
        return None
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def cache_get_json(key: str) -> Any | None:
    """None both when Redis is unavailable and when the key simply isn't
    set -- callers that need to distinguish "not cached" from "cached as
    null" shouldn't cache a literal null value in the first place."""
    client = get_redis()
    if client is None:
        return None
    try:
        # redis-py's stubs type .get() as ResponseT (a union shared with the
        # async client that includes Awaitable[Any]) even though a
        # synchronous Redis with decode_responses=True always returns
        # `str | None` at runtime -- same known stub/runtime mismatch
        # db/connection.py's own _Cursor cast already works around, not a
        # real Awaitable this code could ever receive.
        raw = cast("str | None", client.get(key))
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    """No-ops silently on any Redis failure -- a cache write is never load-
    bearing for correctness (every caller must still be able to read the
    authoritative source on a cache miss), only for avoiding a repeated DB
    round-trip."""
    client = get_redis()
    if client is None:
        return
    try:
        payload = json.dumps(value)
        if ttl_seconds is not None:
            client.setex(key, ttl_seconds, payload)
        else:
            client.set(key, payload)
    except Exception:
        pass


def cache_delete(key: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        pass


def publish(channel: str, message: str) -> None:
    """Fire-and-forget pub/sub publish (portal/permission_cache.py's
    invalidate() uses this for the `perms:invalidate` channel) -- no-ops if
    Redis is unavailable, same as every other function here; a permission
    edit still takes effect (subsequent reads simply miss the now-stale
    local cache and re-read Postgres) even if this specific broadcast never
    reaches other worker processes."""
    client = get_redis()
    if client is None:
        return
    try:
        client.publish(channel, message)
    except Exception:
        pass
