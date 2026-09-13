# portal/permission_cache.py
"""Redis cache + pub/sub invalidation for the per-hospital permission matrix
(docs/rbac-redis-plan.md) -- portal/permissions.py's get_permission_matrix()
is read on every permission-gated request, so caching it avoids a
role_permissions table scan per request; invalidate() below is what makes an
admin's edit in the Roles & Permissions UI take effect immediately for every
already-logged-in staff member at that hospital, on every worker process,
without waiting for a TTL to lapse.

Two layers, both optional and independently degradable:
  1. A process-local dict (_LOCAL_CACHE) -- avoids even a Redis round-trip
     for the common case of the same worker serving many requests for the
     same hospital in a row.
  2. Redis itself (via core/redis_client.py) -- shared across worker
     processes/instances, with its own TTL as a safety net in case a publish
     is ever missed.

No Redis -> get_cached_matrix() always misses (falls through to Postgres via
get_permission_matrix()) and invalidate() only clears the LOCAL dict -- this
whole layer no-ops down to "hit the DB every time," never a 500, matching
this project's stated Redis-optional posture. The startup subscriber
(main.py) is what makes cross-PROCESS invalidation actually work; a
single-process dev server invalidates correctly even without Redis, since
invalidate() always clears its own local entry regardless.

User-level permission overrides (get_cached_overrides/set_cached_overrides/
drop_local_staff_cache/invalidate_staff below) get their OWN parallel local
dict + Redis key per (hospital_id, staff_id) -- editing one person's
override never invalidates the whole hospital's role-permission cache, and
vice versa. Both kinds of invalidation share the same `perms:invalidate`
channel/subscriber (the payload just optionally carries a `staff_id`) rather
than running a second pub/sub thread for what's otherwise an identical
"drop this one cache entry" operation."""
import json

from core.redis_client import cache_delete, cache_get_json, cache_set_json, publish

INVALIDATE_CHANNEL = "perms:invalidate"
_CACHE_TTL_SECONDS = 5 * 60

_LOCAL_CACHE: dict[int, dict] = {}
# Staff-level override cache -- keyed separately from _LOCAL_CACHE above so
# that invalidating one person's overrides never touches (or gets confused
# with) the whole hospital's role-permission matrix cache.
_LOCAL_STAFF_CACHE: dict[tuple[int, int], dict] = {}


def _redis_key(hospital_id: int) -> str:
    return f"perms:matrix:{hospital_id}"


def _staff_redis_key(hospital_id: int, staff_id: int) -> str:
    return f"perms:overrides:{hospital_id}:{staff_id}"


def get_cached_matrix(hospital_id: int) -> dict | None:
    if hospital_id in _LOCAL_CACHE:
        return _LOCAL_CACHE[hospital_id]
    cached = cache_get_json(_redis_key(hospital_id))
    if cached is not None:
        _LOCAL_CACHE[hospital_id] = cached
    return cached


def set_cached_matrix(hospital_id: int, matrix: dict) -> None:
    _LOCAL_CACHE[hospital_id] = matrix
    cache_set_json(_redis_key(hospital_id), matrix, ttl_seconds=_CACHE_TTL_SECONDS)


def get_cached_overrides(hospital_id: int, staff_id: int) -> dict | None:
    """Staff-override counterpart to get_cached_matrix() above -- same
    local-dict-then-Redis fallthrough."""
    key = (hospital_id, staff_id)
    if key in _LOCAL_STAFF_CACHE:
        return _LOCAL_STAFF_CACHE[key]
    cached = cache_get_json(_staff_redis_key(hospital_id, staff_id))
    if cached is not None:
        _LOCAL_STAFF_CACHE[key] = cached
    return cached


def set_cached_overrides(hospital_id: int, staff_id: int, overrides: dict) -> None:
    _LOCAL_STAFF_CACHE[(hospital_id, staff_id)] = overrides
    cache_set_json(_staff_redis_key(hospital_id, staff_id), overrides, ttl_seconds=_CACHE_TTL_SECONDS)


def drop_local_cache(hospital_id: int) -> None:
    """Called by main.py's perms:invalidate subscriber on every OTHER
    worker/instance when it receives a publish -- clears only the local
    dict, not Redis's own copy (the publisher's own invalidate() call below
    already deleted that)."""
    _LOCAL_CACHE.pop(hospital_id, None)


def drop_local_staff_cache(hospital_id: int, staff_id: int) -> None:
    """Staff-override counterpart to drop_local_cache() above -- called by
    main.py's same subscriber when a message carries a `staff_id`."""
    _LOCAL_STAFF_CACHE.pop((hospital_id, staff_id), None)


def invalidate(hospital_id: int) -> None:
    """Called by PUT /api/portal/roles/permissions right after writing the
    changed rows -- deletes this process's local entry AND the shared Redis
    entry, then publishes on `perms:invalidate` so every OTHER worker
    process/instance drops its own local entry too (main.py's startup
    subscriber is what's listening). The publishing process's own local
    cache is cleared directly here rather than round-tripping through its
    own subscriber -- a process is never subscribed to its own pub/sub
    message in a way this code relies on."""
    _LOCAL_CACHE.pop(hospital_id, None)
    cache_delete(_redis_key(hospital_id))
    publish(INVALIDATE_CHANNEL, json.dumps({"hospital_id": hospital_id}))


def invalidate_staff(hospital_id: int, staff_id: int) -> None:
    """Called by PUT /api/portal/staff/{staff_id}/permissions -- same shape
    as invalidate() above, but scoped to one person's override cache only,
    on the SAME `perms:invalidate` channel (the payload just also carries
    `staff_id`; main.py's one subscriber branches on its presence rather
    than needing a second channel/thread for what's otherwise an identical
    invalidate-a-cache-entry operation)."""
    _LOCAL_STAFF_CACHE.pop((hospital_id, staff_id), None)
    cache_delete(_staff_redis_key(hospital_id, staff_id))
    publish(INVALIDATE_CHANNEL, json.dumps({"hospital_id": hospital_id, "staff_id": staff_id}))


def reset_for_tests() -> None:
    """Test-only: clears the local cache between tests, same role
    core/rate_limit.py's reset_all_for_tests() plays for that module's
    singleton. Not called anywhere in application code."""
    _LOCAL_CACHE.clear()
    _LOCAL_STAFF_CACHE.clear()
