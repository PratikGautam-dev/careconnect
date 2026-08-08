import json
import os
import time
from collections import defaultdict

MAX_MESSAGES = 20


class InMemoryHistory:
    def __init__(self, max_messages: int = MAX_MESSAGES):
        self._store: dict[str, list] = defaultdict(list)
        self._max = max_messages

    def add(self, phone: str, role: str, content: str) -> None:
        self._store[phone].append({"role": role, "content": content})
        if len(self._store[phone]) > self._max:
            self._store[phone] = self._store[phone][-self._max:]

    def get(self, phone: str) -> list[dict]:
        return list(self._store[phone])


class RedisHistory:
    def __init__(self, redis_url: str, max_messages: int = MAX_MESSAGES, ttl_seconds: int = 7 * 24 * 3600):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._max = max_messages
        self._ttl = ttl_seconds

    def _key(self, phone: str) -> str:
        return f"history:{phone}"

    def add(self, phone: str, role: str, content: str) -> None:
        key = self._key(phone)
        msgs = self.get(phone)
        msgs.append({"role": role, "content": content})
        if len(msgs) > self._max:
            msgs = msgs[-self._max:]
        self._redis.setex(key, self._ttl, json.dumps(msgs))

    def get(self, phone: str) -> list[dict]:
        key = self._key(phone)
        raw = self._redis.get(key)
        if not raw:
            return []
        return json.loads(raw)


def get_history() -> InMemoryHistory | RedisHistory:
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            h = RedisHistory(redis_url)
            h._redis.ping()
            return h
        except Exception:
            pass
    return InMemoryHistory()


# --- Conversation state (SPEC Section 3.3 state machine) ---
# Same storage mechanism as message history above (Redis with in-memory fallback),
# just a separate key namespace/shape: {"state": str, "context": dict, "language":
# str | None, "updated_at": epoch}.
#
# Keyed by (hospital_id, phone), not phone alone (SPEC Section 12.2 multi-tenant
# routing, Phase 9) — two different hospitals could otherwise collide if the same
# phone number ever messaged both, resuming one hospital's conversation state
# inside another's.
#
# `language` (language-selection follow-up) is deliberately a TOP-LEVEL session
# field, not nested inside `context` -- several state transitions in
# core/booking_flow.py rebuild `context` from scratch rather than spreading the
# old one (e.g. _handle_awaiting_department's `new_context = {"department_id":
# ...}` has no `**context`), so a value nested in `context` would silently get
# dropped partway through a booking. A top-level field, auto-preserved by
# set()/reset() below unless a caller explicitly passes a new one, survives
# every transition without touching every one of those call sites.
#
# reset() deliberately preserves `language` (rather than wiping the whole
# session) when one was already chosen: reset() is called after almost every
# completed action (a booking confirmed, a cancel finished, a reset keyword
# typed) to return to the top-level menu -- wiping language on every one of
# those would re-ask English/Hindi after every single action instead of once
# per genuinely fresh conversation. A session that never had a language
# chosen (or has fully expired past SESSION_TIMEOUT_SECONDS) still resets to
# a clean slate, which is what makes a new/returning-after-a-gap conversation
# get asked again -- "each fresh conversation" per the feature's own intent.
#
# get() omits the "language" key entirely when unset (rather than including
# it as None) so every pre-existing `sessions.get(...) == {"state": ...,
# "context": ...}` equality assertion across the test suite keeps working
# unchanged for sessions that never touch language. Every caller reads it via
# `.get("language")`, which returns None either way, so the omission is
# invisible to real code.

DEFAULT_STATE = "IDLE"
SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 min inactivity -> treat as IDLE on next message


class InMemorySessionStore:
    def __init__(self, timeout_seconds: int = SESSION_TIMEOUT_SECONDS):
        self._store: dict[tuple[int, str], dict] = {}
        self._timeout = timeout_seconds

    def get(self, hospital_id: int, phone: str) -> dict:
        session = self._store.get((hospital_id, phone))
        if session is None or (time.time() - session["updated_at"]) > self._timeout:
            return {"state": DEFAULT_STATE, "context": {}}
        result = {"state": session["state"], "context": session["context"]}
        language = session.get("language")
        if language is not None:
            result["language"] = language
        return result

    def set(self, hospital_id: int, phone: str, state: str, context: dict | None = None, language: str | None = None) -> None:
        existing = self._store.get((hospital_id, phone))
        resolved_language = language if language is not None else (existing.get("language") if existing else None)
        self._store[(hospital_id, phone)] = {
            "state": state,
            "context": context or {},
            "language": resolved_language,
            "updated_at": time.time(),
        }

    def reset(self, hospital_id: int, phone: str) -> None:
        existing = self._store.get((hospital_id, phone))
        language = existing.get("language") if existing else None
        if language:
            self.set(hospital_id, phone, DEFAULT_STATE, {}, language=language)
        else:
            self._store.pop((hospital_id, phone), None)


class RedisSessionStore:
    def __init__(self, redis_url: str, timeout_seconds: int = SESSION_TIMEOUT_SECONDS):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._timeout = timeout_seconds

    def _key(self, hospital_id: int, phone: str) -> str:
        return f"session:{hospital_id}:{phone}"

    def get(self, hospital_id: int, phone: str) -> dict:
        raw = self._redis.get(self._key(hospital_id, phone))
        if not raw:
            return {"state": DEFAULT_STATE, "context": {}}
        session = json.loads(raw)
        if (time.time() - session["updated_at"]) > self._timeout:
            return {"state": DEFAULT_STATE, "context": {}}
        result = {"state": session["state"], "context": session["context"]}
        language = session.get("language")
        if language is not None:
            result["language"] = language
        return result

    def set(self, hospital_id: int, phone: str, state: str, context: dict | None = None, language: str | None = None) -> None:
        raw = self._redis.get(self._key(hospital_id, phone))
        existing = json.loads(raw) if raw else None
        resolved_language = language if language is not None else (existing.get("language") if existing else None)
        session = {"state": state, "context": context or {}, "language": resolved_language, "updated_at": time.time()}
        # Redis TTL is just a cleanup backstop (generous buffer over the soft timeout above,
        # which is what actually governs "reset to IDLE after 30 min").
        self._redis.setex(self._key(hospital_id, phone), self._timeout + 300, json.dumps(session))

    def reset(self, hospital_id: int, phone: str) -> None:
        raw = self._redis.get(self._key(hospital_id, phone))
        existing = json.loads(raw) if raw else None
        language = existing.get("language") if existing else None
        if language:
            self.set(hospital_id, phone, DEFAULT_STATE, {}, language=language)
        else:
            self._redis.delete(self._key(hospital_id, phone))


def get_session_store() -> InMemorySessionStore | RedisSessionStore:
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            s = RedisSessionStore(redis_url)
            s._redis.ping()
            return s
        except Exception:
            pass
    return InMemorySessionStore()
