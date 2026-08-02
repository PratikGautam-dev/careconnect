# tests/test_connectors.py
"""
SPEC Section 12.6.2: the fixed connector interface. Proves Tier1Connector is a
behavior-preserving wrapper around db/repository.py (the refactor this backs
must not change anything for existing Tier 1 hospitals), that Tier2Connector/
Tier3Connector are clearly-stubbed "not yet implemented" paths rather than
speculative logic, and that get_connector_for_hospital is the single
tier-dispatch point.
"""
from datetime import datetime, timedelta

import pytest

import db.repository as db
from connectors import (
    Connector,
    ConnectorNotImplementedError,
    Tier1Connector,
    Tier2Connector,
    Tier3Connector,
    get_connector_for_hospital,
)
from db.connection import IntegrityError


# --- Dispatch ---

def test_get_connector_for_hospital_dispatches_by_data_tier(hospital_id):
    hospital = db.get_hospital(hospital_id)
    assert hospital.data_tier == "tier1"
    assert isinstance(get_connector_for_hospital(hospital), Tier1Connector)


def test_get_connector_for_hospital_dispatches_tier2_and_tier3(hospital_id):
    hospital = db.get_hospital(hospital_id)
    for tier, expected_cls in [("tier2", Tier2Connector), ("tier3", Tier3Connector)]:
        hospital.data_tier = tier  # dataclass instance, safe to mutate for this test only
        assert isinstance(get_connector_for_hospital(hospital), expected_cls)


def test_get_connector_for_hospital_rejects_unrecognized_tier(hospital_id):
    hospital = db.get_hospital(hospital_id)
    hospital.data_tier = "tier99"
    with pytest.raises(ConnectorNotImplementedError):
        get_connector_for_hospital(hospital)


# --- Tier1Connector: must behave identically to calling db/repository.py directly ---

def test_tier1_get_departments_and_doctors_match_repository(hospital_id):
    connector = Tier1Connector()
    assert connector.get_departments(hospital_id) == db.get_departments(hospital_id)
    doctors = db.get_doctors(hospital_id, "cardiology")
    assert connector.get_doctors(hospital_id, "cardiology") == doctors


def test_tier1_get_available_slots_matches_repository(hospital_id):
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    assert connector.get_available_slots(hospital_id, doctor_id) == db.get_slots(hospital_id, doctor_id)


def test_tier1_create_booking_and_double_booking_guard(hospital_id):
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    when = datetime(2027, 1, 1, 10, 0)

    appt = connector.create_booking(hospital_id, "5490001111", "cardiology", doctor_id, when)
    assert appt.phone == "5490001111"

    with pytest.raises(IntegrityError):
        connector.create_booking(hospital_id, "5490002222", "cardiology", doctor_id, when)


def test_tier1_cancel_booking(hospital_id):
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = connector.create_booking(hospital_id, "5490003333", "cardiology", doctor_id, datetime(2027, 1, 2, 10, 0))

    connector.cancel_booking(hospital_id, appt.id)

    remaining = connector.get_upcoming_appointments(hospital_id, phone="5490003333")
    assert remaining == []


def test_tier1_reschedule_booking_books_new_before_touching_old(hospital_id):
    """Mirrors the Phase 8 fix: reschedule_booking must book the new slot
    before marking the old one rescheduled, so a losing race (new slot
    already taken) leaves the patient's original appointment intact."""
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    old_appt = connector.create_booking(hospital_id, "5490004444", "cardiology", doctor_id, datetime(2027, 1, 3, 10, 0))
    new_time = datetime(2027, 1, 3, 15, 0)

    new_appt = connector.reschedule_booking(
        hospital_id, old_appt.id, "5490004444", "cardiology", doctor_id, new_time,
    )

    assert new_appt.scheduled_at == new_time
    old = db.get_appointment(hospital_id, old_appt.id)
    assert old.status == db.STATUS_RESCHEDULED


def test_tier1_reschedule_booking_losing_race_keeps_original_appointment(hospital_id):
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    old_appt = connector.create_booking(hospital_id, "5490005555", "cardiology", doctor_id, datetime(2027, 1, 4, 10, 0))
    contested_time = datetime(2027, 1, 4, 15, 0)
    db.create_appointment(hospital_id, "someone-else", "cardiology", doctor_id, contested_time)  # already taken

    with pytest.raises(IntegrityError):
        connector.reschedule_booking(hospital_id, old_appt.id, "5490005555", "cardiology", doctor_id, contested_time)

    original = db.get_appointment(hospital_id, old_appt.id)
    assert original.status == db.STATUS_BOOKED  # not touched by the failed reschedule attempt


def test_tier1_get_upcoming_appointments_phone_mode(hospital_id):
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    connector.create_booking(hospital_id, "5490006666", "cardiology", doctor_id, datetime.now() + timedelta(hours=5))

    appointments = connector.get_upcoming_appointments(hospital_id, phone="5490006666")

    assert len(appointments) == 1
    assert appointments[0].phone == "5490006666"


def test_tier1_get_upcoming_appointments_offset_mode(hospital_id):
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    connector.create_booking(hospital_id, "5490007777", "cardiology", doctor_id, datetime.now() + timedelta(hours=5))

    due = connector.get_upcoming_appointments(hospital_id, offset_hours=24)

    assert len(due) == 1
    assert due[0].phone == "5490007777"


def test_tier1_get_upcoming_appointments_requires_a_filter(hospital_id):
    connector = Tier1Connector()
    with pytest.raises(ValueError):
        connector.get_upcoming_appointments(hospital_id)


def test_tier1_mark_reminder_sent_prevents_double_send(hospital_id):
    connector = Tier1Connector()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    appt = connector.create_booking(hospital_id, "5490008888", "cardiology", doctor_id, datetime.now() + timedelta(hours=5))

    connector.mark_reminder_sent(hospital_id, appt.id, 24)
    due_again = connector.get_upcoming_appointments(hospital_id, offset_hours=24)

    assert due_again == []  # already reminded for this offset, not returned again


# --- Tier2/Tier3: clearly-stubbed, not speculative logic ---

@pytest.mark.parametrize("connector_cls", [Tier2Connector, Tier3Connector])
@pytest.mark.parametrize("method_name,args", [
    ("get_departments", (1,)),
    ("get_doctors", (1, "dept")),
    ("get_available_slots", (1, "doc")),
    ("create_booking", (1, "555", "dept", "doc", datetime.now())),
    ("cancel_booking", (1, 1)),
    ("reschedule_booking", (1, 1, "555", "dept", "doc", datetime.now())),
    ("get_upcoming_appointments", (1,)),
    ("mark_reminder_sent", (1, 1, 24)),
])
def test_unimplemented_tier_connectors_raise_clear_error_for_every_method(connector_cls, method_name, args):
    connector = connector_cls()
    method = getattr(connector, method_name)
    with pytest.raises(ConnectorNotImplementedError, match="no real connector implementation yet"):
        method(*args)


def test_connector_is_a_real_abstract_base_class():
    """Guards against a future subclass silently missing a method -- Connector
    uses abc.abstractmethod, so instantiating an incomplete subclass must fail
    at class-definition/instantiation time, not silently at call time."""
    with pytest.raises(TypeError):
        class _Incomplete(Connector):
            pass
        _Incomplete()
