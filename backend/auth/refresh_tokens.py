# auth/refresh_tokens.py
"""Opaque, Redis-backed refresh tokens (docs/rbac-redis-plan.md) -- pairs
with auth/jwt_session.py's deliberately short (15-min) access tokens: without
a refresh path, that TTL alone would mean re-entering a password every 15
minutes, which no one would accept. A refresh token is a random opaque
string (not a JWT -- nothing needs to be embedded/inspected client-side, and
opaque tokens are trivially revocable by deleting the Redis key, unlike a
JWT which would need its own token_version-style indirection all over
again), stored server-side as redis:{sha256(token)} -> {staff_id,
hospital_id, role}, 7-day TTL, ROTATED on every use (the old token is
deleted and a new one issued alongside the new access token) -- rotation
means a stolen refresh token that's already been used once by its rightful
owner is worthless to whoever stole it, without needing a separate
"detected reuse -> revoke the whole family" scheme (out of scope at this
project's stated "basic protection, not production-grade auth" posture).

Follows the exact RedisX/InMemoryX dual-class + _build_x() factory pattern
already established by core/rate_limit.py/core/session_store.py (not
core/redis_client.py's simpler get_redis()-per-call shape) because refresh
tokens need a per-process client held across calls the same way those two
modules' state does, and because logout-everywhere (revoke_all_for_staff())
needs a SCAN-like fan-out that's naturally a method on a stateful client
class, not a fits-in-one-call helper. Degrading to the in-memory fallback
when REDIS_URL is unset means logout-everywhere silently loses effect across
a process restart -- an explicitly accepted gap (the plan's own "matching
this project's documented basic-protection posture" line), not a bug."""
import hashlib
import os
import secrets
import time

REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60


def _hash(token: str) -> str:
    """Only the hash is ever stored, never the raw token -- same reasoning
    portal/deps.py's _session_id() already applies to audit-trail tokens: a
    raw refresh token sitting in Redis (or a future admin view of active
    sessions) would itself be a live credential."""
    return hashlib.sha256(token.encode()).hexdigest()


class InMemoryRefreshStore:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def issue(self, staff_id: int, hospital_id: int, role: str) -> str:
        token = secrets.token_urlsafe(32)
        self._store[_hash(token)] = {
            "staff_id": staff_id, "hospital_id": hospital_id, "role": role,
            "expires_at": time.time() + REFRESH_TOKEN_TTL_SECONDS,
        }
        return token

    def consume(self, token: str) -> dict | None:
        key = _hash(token)
        record = self._store.pop(key, None)
        if record is None or record["expires_at"] < time.time():
            return None
        return record

    def revoke(self, token: str) -> None:
        self._store.pop(_hash(token), None)

    def revoke_all_for_staff(self, staff_id: int) -> None:
        for key in [k for k, v in self._store.items() if v["staff_id"] == staff_id]:
            self._store.pop(key, None)


class RedisRefreshStore:
    def __init__(self, redis_url: str):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def _key(self, token_hash: str) -> str:
        return f"refresh:{token_hash}"

    def _staff_index_key(self, staff_id: int) -> str:
        """A Redis SET of this staff member's live token hashes -- the index
        revoke_all_for_staff() walks instead of a KEYS/SCAN over the whole
        keyspace (unsafe/slow against a shared production Redis instance).
        Entries here can outlive their own refresh: token key (naturally
        expired via its own TTL, never cleaned out of this set), so
        revoke_all_for_staff() tolerates a delete() no-op for an already-gone
        member -- see its own comment."""
        return f"refresh:staff:{staff_id}"

    def issue(self, staff_id: int, hospital_id: int, role: str) -> str:
        import json
        token = secrets.token_urlsafe(32)
        token_hash = _hash(token)
        pipe = self._redis.pipeline()
        pipe.setex(
            self._key(token_hash), REFRESH_TOKEN_TTL_SECONDS,
            json.dumps({"staff_id": staff_id, "hospital_id": hospital_id, "role": role}),
        )
        pipe.sadd(self._staff_index_key(staff_id), token_hash)
        pipe.expire(self._staff_index_key(staff_id), REFRESH_TOKEN_TTL_SECONDS)
        pipe.execute()
        return token

    def consume(self, token: str) -> dict | None:
        import json
        token_hash = _hash(token)
        raw = self._redis.get(self._key(token_hash))
        if raw is None:
            return None
        # Delete-on-read (not delete-on-issue-of-the-next-one) is what makes
        # this rotation, not just "an unexpiring bearer credential with extra
        # steps" -- a token can only ever be consumed once.
        self._redis.delete(self._key(token_hash))
        self._redis.srem(self._staff_index_key(json.loads(raw)["staff_id"]), token_hash)
        return json.loads(raw)

    def revoke(self, token: str) -> None:
        self._redis.delete(self._key(_hash(token)))

    def revoke_all_for_staff(self, staff_id: int) -> None:
        index_key = self._staff_index_key(staff_id)
        token_hashes = self._redis.smembers(index_key)
        if token_hashes:
            self._redis.delete(*[self._key(h) for h in token_hashes])
        self._redis.delete(index_key)


def _build_store() -> "InMemoryRefreshStore | RedisRefreshStore":
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            store = RedisRefreshStore(redis_url)
            store._redis.ping()
            return store
        except Exception:
            pass
    return InMemoryRefreshStore()


_STORE = _build_store()


def issue_refresh_token(staff_id: int, hospital_id: int, role: str) -> str:
    return _STORE.issue(staff_id, hospital_id, role)


def consume_refresh_token(token: str) -> dict | None:
    """Returns {staff_id, hospital_id, role} and deletes the token (single-
    use) if valid/unexpired, else None. The refresh route re-fetches the
    staff row fresh from Postgres before issuing a new access token, rather
    than trusting hospital_id/role straight out of this record -- a role
    change since the token was issued must take effect on refresh, not be
    perpetuated by a stale cached value here."""
    return _STORE.consume(token)


def revoke_refresh_token(token: str) -> None:
    """Single-device logout (POST /api/portal/staff/logout)."""
    _STORE.revoke(token)


def revoke_all_for_staff(staff_id: int) -> None:
    """Logout-everywhere -- called by a future admin "force logout" action
    and by update_staff_user_password()/set_staff_user_active() callers that
    want refresh tokens killed alongside the access-token token_version bump
    (not wired to those automatically here, since not every token_version
    bump should force a refresh-token wipe too -- see the staff_auth route
    for where this is actually invoked)."""
    _STORE.revoke_all_for_staff(staff_id)


def reset_for_tests() -> None:
    """Test-only: mirrors core/rate_limit.py's reset_all_for_tests() -- gives
    each test a clean slate. Not called anywhere in application code."""
    global _STORE
    _STORE = InMemoryRefreshStore()
