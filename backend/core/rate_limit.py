"""Shared login/secret-check rate limiting -- audit follow-up (Spec.md
Section 0): portal login, ADMIN_SECRET, and TENANTS_ADMIN_SECRET previously
allowed unlimited guesses. Same Redis-with-in-memory-fallback pattern as
core/session_store.py's session store (connect once, fall back silently if Redis
isn't reachable), just a per-key failure counter instead of session state.

Deliberately simple, matching this project's own stated "basic protection,
not production-grade auth" posture (see portal.py's module docstring):
a fixed-window failure count per key, no sliding window, no distributed
clock skew handling. Keyed by caller IP (core/main.py's own established
pattern has no per-account identity to key by either at this stage -- these
are shared secrets, not per-user credentials) -- proxied deployments sharing
one IP is a known limitation of this simple approach, not solved here."""
import os
import time
from collections import defaultdict

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW_SECONDS = 15 * 60  # 15 minutes


class InMemoryRateLimiter:
    def __init__(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._max = max_attempts
        self._window = window_seconds

    def _prune(self, key: str) -> list[float]:
        now = time.time()
        fresh = [t for t in self._attempts[key] if now - t < self._window]
        self._attempts[key] = fresh
        return fresh

    def is_locked_out(self, key: str) -> bool:
        return len(self._prune(key)) >= self._max

    def record_failure(self, key: str) -> None:
        self._prune(key)
        self._attempts[key].append(time.time())

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


class RedisRateLimiter:
    def __init__(self, redis_url: str, max_attempts: int = DEFAULT_MAX_ATTEMPTS, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._max = max_attempts
        self._window = window_seconds

    def _key(self, key: str) -> str:
        return f"ratelimit:{key}"

    def is_locked_out(self, key: str) -> bool:
        count = self._redis.get(self._key(key))
        return count is not None and int(count) >= self._max

    def record_failure(self, key: str) -> None:
        redis_key = self._key(key)
        pipe = self._redis.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, self._window)
        pipe.execute()

    def reset(self, key: str) -> None:
        self._redis.delete(self._key(key))


def _build_limiter() -> "InMemoryRateLimiter | RedisRateLimiter":
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            r = RedisRateLimiter(redis_url)
            r._redis.ping()
            return r
        except Exception:
            pass
    return InMemoryRateLimiter()


_LIMITER = _build_limiter()


def is_locked_out(key: str) -> bool:
    return _LIMITER.is_locked_out(key)


def record_failure(key: str) -> None:
    _LIMITER.record_failure(key)


def reset(key: str) -> None:
    _LIMITER.reset(key)


def reset_all_for_tests() -> None:
    """Test-only: gives every test a clean rate-limit slate, same role as
    conftest.py's _fresh_test_db fixture does for the database. Not called
    anywhere in application code."""
    global _LIMITER
    _LIMITER = InMemoryRateLimiter()


def client_key(scope: str, request) -> str:
    """A rate-limit key for one FastAPI Request, namespaced by `scope` (e.g.
    "portal_login", "admin_secret") so unrelated endpoints don't share a
    lockout counter. `request.client` is None in some test/ASGI-transport
    setups, hence the fallback."""
    ip = request.client.host if request is not None and request.client else "unknown"
    return f"{scope}:{ip}"
