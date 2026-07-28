import time

import pytest
from core.history import (
    InMemoryHistory,
    InMemorySessionStore,
    RedisHistory,
    RedisSessionStore,
    get_history,
    get_session_store,
)

MAX = 20

def test_in_memory_add_and_get():
    h = InMemoryHistory()
    h.add("phone1", "user", "hello")
    h.add("phone1", "assistant", "hi")
    msgs = h.get("phone1")
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "hello"}
    assert msgs[1] == {"role": "assistant", "content": "hi"}

def test_in_memory_max_messages():
    h = InMemoryHistory(max_messages=MAX)
    for i in range(25):
        h.add("phone1", "user", f"msg {i}")
    assert len(h.get("phone1")) == MAX

def test_in_memory_different_phones_isolated():
    h = InMemoryHistory()
    h.add("phone1", "user", "msg for 1")
    h.add("phone2", "user", "msg for 2")
    assert len(h.get("phone1")) == 1
    assert h.get("phone1")[0]["content"] == "msg for 1"

def test_get_history_returns_in_memory_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    h = get_history()
    assert isinstance(h, InMemoryHistory)


# --- Session store (conversation state machine, SPEC Section 3.3) ---
# Keyed by (hospital_id, phone) — SPEC Section 12.2/Phase 9 multi-tenant routing.

HOSPITAL_A = 1
HOSPITAL_B = 2


def test_session_defaults_to_idle_with_empty_context():
    s = InMemorySessionStore()
    session = s.get(HOSPITAL_A, "phone1")
    assert session == {"state": "IDLE", "context": {}}


def test_session_set_and_get_roundtrip():
    s = InMemorySessionStore()
    s.set(HOSPITAL_A, "phone1", "AWAITING_DEPARTMENT", {"foo": "bar"})
    session = s.get(HOSPITAL_A, "phone1")
    assert session["state"] == "AWAITING_DEPARTMENT"
    assert session["context"] == {"foo": "bar"}


def test_session_reset_returns_to_idle():
    s = InMemorySessionStore()
    s.set(HOSPITAL_A, "phone1", "AWAITING_DOCTOR", {"department_id": "cardiology"})
    s.reset(HOSPITAL_A, "phone1")
    assert s.get(HOSPITAL_A, "phone1") == {"state": "IDLE", "context": {}}


def test_session_different_phones_isolated():
    s = InMemorySessionStore()
    s.set(HOSPITAL_A, "phone1", "AWAITING_SLOT", {"doctor_id": "doc1"})
    session = s.get(HOSPITAL_A, "phone2")
    assert session == {"state": "IDLE", "context": {}}


def test_session_different_hospitals_isolated_even_with_same_phone():
    """SPEC Section 12.2: two different hospitals must never share session
    state, even if (unusually) the same phone number messages both."""
    s = InMemorySessionStore()
    s.set(HOSPITAL_A, "shared_phone", "AWAITING_CONFIRMATION", {"doctor_name": "Dr. A"})
    session_b = s.get(HOSPITAL_B, "shared_phone")
    assert session_b == {"state": "IDLE", "context": {}}
    # And hospital A's own session is untouched by reading hospital B's.
    assert s.get(HOSPITAL_A, "shared_phone")["state"] == "AWAITING_CONFIRMATION"


def test_session_times_out_after_timeout_window():
    s = InMemorySessionStore(timeout_seconds=1)
    s.set(HOSPITAL_A, "phone1", "AWAITING_CONFIRMATION", {"slot_id": "x"})
    assert s.get(HOSPITAL_A, "phone1")["state"] == "AWAITING_CONFIRMATION"
    time.sleep(1.1)
    assert s.get(HOSPITAL_A, "phone1") == {"state": "IDLE", "context": {}}


def test_get_session_store_returns_in_memory_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    s = get_session_store()
    assert isinstance(s, InMemorySessionStore)
