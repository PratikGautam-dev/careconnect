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
# Section 12.13: .get() takes an optional per-call timeout_seconds, since a
# hospital can override the fixed 30-min SESSION_TIMEOUT_SECONDS default
# (hospitals.session_timeout_minutes) -- this ONE store instance is shared
# across every hospital, so the override has to travel with each call rather
# than being fixed at construction time.
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

    def get(self, hospital_id: int, phone: str, timeout_seconds: int | None = None) -> dict:
        # Section 12.13: a hospital can override the fixed 30-min default
        # (hospitals.session_timeout_minutes, 5-120) -- passed in per-call
        # since this ONE store instance is shared across every hospital, not
        # constructed fresh per hospital.
        timeout = timeout_seconds if timeout_seconds is not None else self._timeout
        session = self._store.get((hospital_id, phone))
        if session is None or (time.time() - session["updated_at"]) > timeout:
            return {"state": DEFAULT_STATE, "context": {}}
        result = {"state": session["state"], "context": session["context"]}
        language = session.get("language")
        if language is not None:
            result["language"] = language
        active_patient_id = session.get("active_patient_id")
        if active_patient_id is not None:
            result["active_patient_id"] = active_patient_id
        return result

    def set(
        self, hospital_id: int, phone: str, state: str, context: dict | None = None, language: str | None = None,
        active_patient_id: int | None = None,
    ) -> None:
        existing = self._store.get((hospital_id, phone))
        resolved_language = language if language is not None else (existing.get("language") if existing else None)
        # CareConnect architecture doc alignment (Spec.md Section 0), Section
        # 13's "Active Patient Context" -- a TOP-LEVEL session field, same
        # treatment as `language` above and for the exact same reason: many
        # state transitions rebuild `context` from scratch rather than
        # spreading the old one, so a value nested in `context` would
        # silently get dropped partway through a flow. Resolved ONCE per
        # conversation (core/patient_identity.py, before the main menu is
        # ever shown) and then auto-preserved across every set()/reset()
        # call for the rest of that session, same "only ask once" pattern
        # language already established -- NOT re-resolved on every booking/
        # cancel/menu return.
        resolved_active_patient_id = (
            active_patient_id if active_patient_id is not None
            else (existing.get("active_patient_id") if existing else None)
        )
        self._store[(hospital_id, phone)] = {
            "state": state,
            "context": context or {},
            "language": resolved_language,
            "active_patient_id": resolved_active_patient_id,
            "updated_at": time.time(),
        }

    def clear_active_patient(self, hospital_id: int, phone: str) -> None:
        """Forces re-resolution on the next message -- used when the
        currently-active patient is unlinked (Manage Patients, self-unlink)
        so a stale active_patient_id can't silently keep being used for the
        rest of this session. Leaves state/context/language untouched."""
        existing = self._store.get((hospital_id, phone))
        if existing is not None:
            existing["active_patient_id"] = None

    def reset(self, hospital_id: int, phone: str, keep_language: bool = True) -> None:
        """Section 12.11 established preserving language across every
        reset(), so a patient is only asked once per genuinely fresh
        conversation, not after every booking/cancel/reset -- still the
        default here (keep_language=True). Follow-up (Spec.md Section 0):
        the ONE exception is a just-COMPLETED booking specifically --
        core/booking_flow.py's confirm-success path passes
        keep_language=False so the language picker is shown again next time,
        while every other reset() call site (cancel, decline, FAQ exit,
        stale-session cleanup, ...) is untouched and keeps preserving it.

        active_patient_id is ALWAYS preserved across reset() (Section 13 --
        resolved once per conversation, not per action) -- there is
        deliberately no keep_active_patient=False variant, unlike language's
        keep_language=False: a fully completed booking clearing the chosen
        LANGUAGE is a deliberate re-ask-preference choice, but there's no
        equivalent "re-resolve which patient this is" trigger anywhere in
        this codebase -- that only ever happens via clear_active_patient()
        (an explicit unlink of the active patient) or a genuine session
        timeout (get()'s own expiry branch, which returns a session with
        neither field at all)."""
        existing = self._store.get((hospital_id, phone))
        language = existing.get("language") if (existing and keep_language) else None
        active_patient_id = existing.get("active_patient_id") if existing else None
        if language is None and active_patient_id is None:
            self._store.pop((hospital_id, phone), None)
            return
        # Deliberately NOT self.set() -- that method treats language=None as
        # "not specified, inherit the existing value" (the same ambiguity
        # clear_active_patient() exists to work around for the other field),
        # which would silently un-clear language here whenever
        # active_patient_id alone needed preserving (keep_language=False but
        # an active patient exists) -- a real bug caught by
        # tests/test_flows.py::test_language_persists_across_a_full_booking_flow_in_hindi.
        # Writing the record directly bypasses that inheritance entirely.
        self._store[(hospital_id, phone)] = {
            "state": DEFAULT_STATE, "context": {}, "language": language,
            "active_patient_id": active_patient_id, "updated_at": time.time(),
        }


class RedisSessionStore:
    def __init__(self, redis_url: str, timeout_seconds: int = SESSION_TIMEOUT_SECONDS):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._timeout = timeout_seconds

    def _key(self, hospital_id: int, phone: str) -> str:
        return f"session:{hospital_id}:{phone}"

    def get(self, hospital_id: int, phone: str, timeout_seconds: int | None = None) -> dict:
        timeout = timeout_seconds if timeout_seconds is not None else self._timeout
        raw = self._redis.get(self._key(hospital_id, phone))
        if not raw:
            return {"state": DEFAULT_STATE, "context": {}}
        session = json.loads(raw)
        if (time.time() - session["updated_at"]) > timeout:
            return {"state": DEFAULT_STATE, "context": {}}
        result = {"state": session["state"], "context": session["context"]}
        language = session.get("language")
        if language is not None:
            result["language"] = language
        active_patient_id = session.get("active_patient_id")
        if active_patient_id is not None:
            result["active_patient_id"] = active_patient_id
        return result

    def set(
        self, hospital_id: int, phone: str, state: str, context: dict | None = None, language: str | None = None,
        active_patient_id: int | None = None,
    ) -> None:
        raw = self._redis.get(self._key(hospital_id, phone))
        existing = json.loads(raw) if raw else None
        resolved_language = language if language is not None else (existing.get("language") if existing else None)
        # See InMemorySessionStore.set()'s own docstring for why this is a
        # top-level field, mirrored identically here.
        resolved_active_patient_id = (
            active_patient_id if active_patient_id is not None
            else (existing.get("active_patient_id") if existing else None)
        )
        session = {
            "state": state, "context": context or {}, "language": resolved_language,
            "active_patient_id": resolved_active_patient_id, "updated_at": time.time(),
        }
        # Redis TTL is just a cleanup backstop (generous buffer over the soft timeout above,
        # which is what actually governs "reset to IDLE after 30 min").
        self._redis.setex(self._key(hospital_id, phone), self._timeout + 300, json.dumps(session))

    def clear_active_patient(self, hospital_id: int, phone: str) -> None:
        """See InMemorySessionStore.clear_active_patient()'s own docstring."""
        raw = self._redis.get(self._key(hospital_id, phone))
        if not raw:
            return
        session = json.loads(raw)
        session["active_patient_id"] = None
        remaining_ttl = self._redis.ttl(self._key(hospital_id, phone))
        self._redis.setex(self._key(hospital_id, phone), remaining_ttl if remaining_ttl > 0 else self._timeout, json.dumps(session))

    def reset(self, hospital_id: int, phone: str, keep_language: bool = True) -> None:
        """See InMemorySessionStore.reset()'s docstring -- identical
        keep_language/active_patient_id semantics, mirrored here for the
        Redis backend."""
        raw = self._redis.get(self._key(hospital_id, phone))
        existing = json.loads(raw) if raw else None
        language = existing.get("language") if (existing and keep_language) else None
        active_patient_id = existing.get("active_patient_id") if existing else None
        if language is None and active_patient_id is None:
            self._redis.delete(self._key(hospital_id, phone))
            return
        # See InMemorySessionStore.reset()'s own comment -- self.set() would
        # silently un-clear language here via its "None means inherit"
        # fallback; writing the record directly avoids that.
        session = {
            "state": DEFAULT_STATE, "context": {}, "language": language,
            "active_patient_id": active_patient_id, "updated_at": time.time(),
        }
        self._redis.setex(self._key(hospital_id, phone), self._timeout + 300, json.dumps(session))


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
