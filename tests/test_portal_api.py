# tests/test_portal_api.py
"""
Audit follow-up (Spec.md Section 0): portal_api.py -- the entire JSON API the
Next.js staff portal runs on -- had zero test coverage before this file,
despite being wired into core/main.py and used by every /portal/* page.
Covers, per the audit's explicit checklist:

  - hospital A cannot cancel, message, toggle, or otherwise read/mutate
    hospital B's doctors/bookings/handoff requests/patients via ID guessing,
    on every mutating (and several read) /api/portal/* route
  - CSV bulk doctor import: success, per-row error isolation, get-or-create
    department by name (case-insensitive)
  - the human-handoff reply endpoint: mocked WhatsAppClient (no real HTTP
    call), correct per-hospital credentials used, does NOT auto-resolve
  - appointment-cancel-with-message: message sent only after the cancel
    commits, and a WhatsApp send failure never turns a successful cancel
    into an error response (portal_cancel_booking's try/except)
  - doctor active/inactive toggle, and that it actually affects the
    bot-facing db.get_doctors() list (the real enforcement point)
  - list_patients/search_patients/get_recent_patients via
    GET /api/portal/patients and the dashboard's "recent_patients" field

A real (minor) cross-tenant gap was found and fixed while writing this:
portal_add_doctor_leave/portal_get_doctor_leave never verified doctor_id
belonged to the authenticated hospital before reading/writing doctor_leave
rows -- db.create_doctor_leave() itself has no way to know, since its INSERT
succeeds regardless of which hospital actually owns that doctor_id. Fixed in
portal_api.py by checking db.get_doctor_full(hospital.id, doctor_id) first,
same pattern portal_create_doctor() already used for department_id.
"""
import os
from datetime import datetime

import pytest

import db.repository as db
import portal_api

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


# --- shared setup helpers ---


def _set_hospital_creds(hospital_id: int, *, password: str, phone_number_id: str, access_token: str) -> None:
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id,
        name=h.name,
        whatsapp_phone_number_id=phone_number_id,
        access_token=access_token,
        app_secret=h.app_secret,
        timezone=h.timezone,
        welcome_message_text=h.welcome_message_text,
        reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name,
        data_tier=h.data_tier,
        external_api_base_url=h.external_api_base_url,
        external_api_key=h.external_api_key,
        portal_password_hash=db.hash_portal_password(password),
        enabled_features=h.enabled_features,
    )


def _login(password: str) -> str:
    resp = client.post("/api/portal/login", json={"password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_appointment(hospital_id: int, doctor_id: str, department_id: str, phone: str = "5490001111", patient_name=None):
    slot = db.get_slots(hospital_id, doctor_id)[0]
    scheduled_at = datetime.fromisoformat(slot["id"])
    return db.create_appointment(hospital_id, phone, department_id, doctor_id, scheduled_at, patient_name=patient_name)


@pytest.fixture
def two_hospitals(hospital_id, second_hospital_id):
    """hospital_id/second_hospital_id (tests/conftest.py) are the two seeded
    tenants -- distinct portal passwords + distinct fake WhatsApp credentials,
    so tests can log in as either and prove neither sees or can act on the
    other's data, and that outgoing sends use the right hospital's creds.
    Hospital A uses doc_card_1/cardiology (seed_default_hospital); Hospital B
    uses t2_doc_neuro_1/t2_neurology (seed_test_hospital)."""
    _set_hospital_creds(hospital_id, password="hospital-a-pw", phone_number_id="hospital-a-phone", access_token="hospital-a-token")
    _set_hospital_creds(second_hospital_id, password="hospital-b-pw", phone_number_id="hospital-b-phone", access_token="hospital-b-token")
    return {
        "a": {"id": hospital_id, "token": _login("hospital-a-pw"), "doctor_id": "doc_card_1", "department_id": "cardiology"},
        "b": {"id": second_hospital_id, "token": _login("hospital-b-pw"), "doctor_id": "t2_doc_neuro_1", "department_id": "t2_neurology"},
    }


@pytest.fixture
def fake_whatsapp_send(monkeypatch):
    """Records every WhatsAppClient.send_text() call along with which
    instance made it (so tests can assert which hospital's credentials were
    used) -- no real HTTP call ever happens."""
    calls = []

    async def fake_send_text(self, to, text):
        calls.append({"phone_number_id": self._phone_number_id, "access_token": self._token, "to": to, "text": text})

    monkeypatch.setattr(portal_api.WhatsAppClient, "send_text", fake_send_text)
    return calls


# --- Multi-tenant isolation: cancel, message, toggle, and read every
# mutating/sensitive /api/portal/* route via cross-hospital ID guessing ---


def test_cancel_booking_cannot_target_other_hospitals_appointment(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    appt_b = _create_appointment(b["id"], b["doctor_id"], b["department_id"])

    resp = client.post(f"/api/portal/bookings/{appt_b.id}/cancel", headers=_auth(a["token"]))
    assert resp.status_code == 404

    # Never actually cancelled.
    still_booked = db.get_appointment(b["id"], appt_b.id)
    assert still_booked.status == db.STATUS_BOOKED


def test_mark_attendance_cannot_target_other_hospitals_appointment(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    appt_b = _create_appointment(b["id"], b["doctor_id"], b["department_id"])

    resp = client.post(
        f"/api/portal/bookings/{appt_b.id}/attendance", json={"attended": True}, headers=_auth(a["token"]),
    )
    assert resp.status_code == 404
    assert db.get_appointment(b["id"], appt_b.id).status == db.STATUS_BOOKED


def test_mark_attendance_attended_and_no_show(two_hospitals):
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])

    resp = client.post(
        f"/api/portal/bookings/{appt.id}/attendance", json={"attended": True}, headers=_auth(a["token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "attended"
    assert db.get_appointment(a["id"], appt.id).status == db.STATUS_ATTENDED

    appt2 = _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490002222")
    resp2 = client.post(
        f"/api/portal/bookings/{appt2.id}/attendance", json={"attended": False}, headers=_auth(a["token"]),
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "no_show"
    assert db.get_appointment(a["id"], appt2.id).status == db.STATUS_NO_SHOW


def test_mark_attendance_twice_is_rejected_not_silently_overwritten(two_hospitals):
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])

    resp1 = client.post(
        f"/api/portal/bookings/{appt.id}/attendance", json={"attended": True}, headers=_auth(a["token"]),
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        f"/api/portal/bookings/{appt.id}/attendance", json={"attended": False}, headers=_auth(a["token"]),
    )
    assert resp2.status_code == 404
    # Still 'attended' from the first call -- the second didn't overwrite it.
    assert db.get_appointment(a["id"], appt.id).status == db.STATUS_ATTENDED


def test_needs_attendance_review_lists_only_past_still_booked_appointments(two_hospitals):
    from datetime import timedelta

    a = two_hospitals["a"]
    past_appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490003333")
    # Backdate it directly -- _create_appointment() always books a real,
    # future slot (db/repository.py never generates past ones).
    conn = db.get_connection()
    conn.execute(
        "UPDATE appointments SET scheduled_at = ? WHERE id = ?",
        ((datetime.now() - timedelta(hours=2)).isoformat(), past_appt.id),
    )
    conn.commit()

    future_appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490004444")

    resp = client.get("/api/portal/bookings/needs-attendance-review", headers=_auth(a["token"]))
    assert resp.status_code == 200, resp.text
    ids = {row["id"] for row in resp.json()["appointments"]}
    assert past_appt.id in ids
    assert future_appt.id not in ids


def test_toggle_doctor_active_cannot_target_other_hospitals_doctor(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]

    resp = client.post(
        f"/api/portal/doctors/{b['doctor_id']}/active", json={"is_active": False}, headers=_auth(a["token"])
    )
    assert resp.status_code == 404

    # Hospital B's doctor is untouched -- still active, still bookable.
    assert any(d["id"] == b["doctor_id"] for d in db.get_doctors(b["id"], b["department_id"]))


def test_doctor_leave_endpoints_cannot_target_other_hospitals_doctor(two_hospitals):
    """Covers the real gap found+fixed while writing this file (see module
    docstring): GET/POST both need the ownership check, not just the delete
    endpoint (which was already safe via its own WHERE clause)."""
    a, b = two_hospitals["a"], two_hospitals["b"]

    get_resp = client.get(f"/api/portal/doctors/{b['doctor_id']}/leave", headers=_auth(a["token"]))
    assert get_resp.status_code == 404

    add_resp = client.post(
        f"/api/portal/doctors/{b['doctor_id']}/leave", json={"date": "2027-01-01"}, headers=_auth(a["token"])
    )
    assert add_resp.status_code == 404
    assert db.get_doctor_leave(b["id"], b["doctor_id"]) == []  # nothing was inserted under B


def test_doctor_leave_range_endpoint_cannot_target_other_hospitals_doctor(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]

    resp = client.post(
        f"/api/portal/doctors/{b['doctor_id']}/leave/range",
        json={"from_date": "2027-01-01", "to_date": "2027-01-03"}, headers=_auth(a["token"]),
    )
    assert resp.status_code == 404
    assert db.get_doctor_leave(b["id"], b["doctor_id"]) == []


def test_doctor_leave_range_creates_one_row_per_day_and_excludes_slots(two_hospitals):
    """Item 10 (Spec.md Section 0): a 3-day range creates 3 leave rows in one
    call, and the doctor's slots are regenerated excluding every date in
    that range -- composes with the existing exclusion logic (Section 14.7)
    with no separate availability-toggle mechanism needed."""
    a = two_hospitals["a"]
    doctor_id = a["doctor_id"]
    before_slots = {s["date"] for s in db.get_slots(a["id"], doctor_id)}
    from_date, to_date = sorted(before_slots)[0], sorted(before_slots)[2]

    resp = client.post(
        f"/api/portal/doctors/{doctor_id}/leave/range",
        json={"from_date": from_date, "to_date": to_date, "reason": "Conference"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["dates"]) == 3

    leave_dates = {row["date"] for row in db.get_doctor_leave(a["id"], doctor_id)}
    assert {from_date, to_date} <= leave_dates

    after_slots = {s["date"] for s in db.get_slots(a["id"], doctor_id)}
    assert from_date not in after_slots
    assert to_date not in after_slots


def test_doctor_leave_range_rejects_to_before_from(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        f"/api/portal/doctors/{a['doctor_id']}/leave/range",
        json={"from_date": "2027-01-05", "to_date": "2027-01-01"}, headers=_auth(a["token"]),
    )
    assert resp.status_code == 400


def test_resolve_handoff_cannot_target_other_hospitals_handoff(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    handoff_b = db.create_handoff_request(b["id"], "919876500000", reason="patient_requested")

    resp = client.post(f"/api/portal/handoffs/{handoff_b['id']}/resolve", headers=_auth(a["token"]))
    assert resp.status_code == 404

    still_open = db.get_handoff_requests(b["id"], status="open")
    assert any(h["id"] == handoff_b["id"] for h in still_open)


def test_reply_handoff_cannot_target_other_hospitals_handoff(two_hospitals, fake_whatsapp_send):
    a, b = two_hospitals["a"], two_hospitals["b"]
    handoff_b = db.create_handoff_request(b["id"], "919876500000", reason="patient_requested")

    resp = client.post(
        f"/api/portal/handoffs/{handoff_b['id']}/reply", json={"text": "hi from the wrong hospital"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 404
    assert fake_whatsapp_send == []  # no message was ever sent


def test_doctors_list_never_includes_other_hospitals_doctors(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    resp = client.get("/api/portal/doctors", headers=_auth(a["token"]))
    assert resp.status_code == 200
    doctor_ids = {d["id"] for d in resp.json()["doctors"]}
    assert b["doctor_id"] not in doctor_ids
    assert a["doctor_id"] in doctor_ids

    dept_ids = {d["id"] for d in resp.json()["departments"]}
    assert b["department_id"] not in dept_ids


def test_create_doctor_rejects_other_hospitals_department_id(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    resp = client.post(
        "/api/portal/doctors",
        json={"department_id": b["department_id"], "name": "Dr. Cross Tenant", "working_days": ["Mon"],
              "working_hours": ["09:00-10:00"], "slot_duration_minutes": "30"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 400
    assert "valid department" in resp.json()["error"]


def test_patients_list_never_includes_other_hospitals_patients(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490001111", patient_name="Patient A")
    _create_appointment(b["id"], b["doctor_id"], b["department_id"], phone="5490002222", patient_name="Patient B")

    resp = client.get("/api/portal/patients", headers=_auth(a["token"]))
    assert resp.status_code == 200
    phones = {p["phone"] for p in resp.json()["patients"]}
    assert "5490001111" in phones
    assert "5490002222" not in phones


def test_bookings_list_never_includes_other_hospitals_appointments(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    appt_a = _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490001111")
    _create_appointment(b["id"], b["doctor_id"], b["department_id"], phone="5490002222")

    resp = client.get("/api/portal/bookings", headers=_auth(a["token"]))
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()["appointments"]}
    assert appt_a.id in ids
    assert len(resp.json()["appointments"]) == 1  # not hospital B's appointment too


def test_dashboard_scoped_to_own_hospital_only(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490001111")
    _create_appointment(b["id"], b["doctor_id"], b["department_id"], phone="5490002222")
    _create_appointment(b["id"], b["doctor_id"], b["department_id"], phone="5490003333")

    resp = client.get("/api/portal/dashboard", headers=_auth(a["token"]))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recent_appointments"]) == 1
    assert data["recent_patients"] == [] or all(p["phone"] != "5490002222" for p in data["recent_patients"])


def test_dashboard_recent_appointments_includes_patient_name_when_on_file(two_hospitals):
    """Item 3 (Spec.md Section 0): the dashboard's separate Patients widget
    was merged into Recent Appointments -- patient name must be inline on
    each row now, not just the phone number."""
    a = two_hospitals["a"]
    _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490004444", patient_name="Merged Widget Patient")

    resp = client.get("/api/portal/dashboard", headers=_auth(a["token"]))
    assert resp.status_code == 200
    row = next(r for r in resp.json()["recent_appointments"] if r["phone"] == "5490004444")
    assert row["patient_name"] == "Merged Widget Patient"


def test_handoffs_list_never_includes_other_hospitals_requests(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    db.create_handoff_request(a["id"], "919876500001", reason="patient_requested")
    db.create_handoff_request(b["id"], "919876500002", reason="patient_requested")

    resp = client.get("/api/portal/handoffs?status=all", headers=_auth(a["token"]))
    assert resp.status_code == 200
    phones = {h["phone"] for h in resp.json()["handoffs"]}
    assert phones == {"919876500001"}


# --- CSV bulk import ---


def _csv_row(**overrides) -> dict:
    row = {
        "department_name": "Radiology",
        "name": "Dr. CSV Import",
        "specialization": "Imaging",
        "qualification": "MD",
        "years_experience": "5",
        "working_days": "Mon,Tue,Wed",
        "working_hours": "09:00-12:00",
        "slot_duration_minutes": "30",
        "breaks": "",
        "max_bookings_per_slot": "1",
        "daily_booking_limit": "",
        "online_quota": "",
        "walkin_quota": "",
        "followup_duration_minutes": "",
        "effective_from": "",
    }
    row.update(overrides)
    return row


def test_csv_import_creates_doctors_and_new_department(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/doctors/csv-import", json={"rows": [_csv_row()]}, headers=_auth(a["token"])
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 1
    assert body["row_errors"] == []

    doctors = db.get_all_doctors_for_hospital(a["id"])
    assert any(d["name"] == "Dr. CSV Import" and d["department_name"] == "Radiology" for d in doctors)


def test_csv_import_reuses_existing_department_case_insensitive(two_hospitals):
    a = two_hospitals["a"]
    # "Cardiology" already exists (seed_default_hospital) -- a differently-cased
    # name in the CSV must reuse it, not create a duplicate "cardiology"/"Cardiology" pair.
    resp = client.post(
        "/api/portal/doctors/csv-import",
        json={"rows": [_csv_row(department_name="CARDIOLOGY", name="Dr. Case Insensitive")]},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["created_count"] == 1

    departments = db.get_departments(a["id"])
    cardiology_depts = [d for d in departments if d["name"].lower() == "cardiology"]
    assert len(cardiology_depts) == 1


def test_csv_import_row_errors_dont_block_good_rows(two_hospitals):
    a = two_hospitals["a"]
    rows = [
        _csv_row(name="Dr. Good One"),
        _csv_row(name="", department_name="Radiology"),  # missing name -- should fail validation
        _csv_row(name="Dr. Good Two", department_name="Radiology"),
    ]
    resp = client.post("/api/portal/doctors/csv-import", json={"rows": rows}, headers=_auth(a["token"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 2
    assert len(body["row_errors"]) == 1
    assert "Row 2" in body["row_errors"][0]

    names = {d["name"] for d in db.get_all_doctors_for_hospital(a["id"])}
    assert "Dr. Good One" in names
    assert "Dr. Good Two" in names


def test_csv_import_missing_department_name_is_a_row_error(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/doctors/csv-import", json={"rows": [_csv_row(department_name="")]}, headers=_auth(a["token"])
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert "department_name is required" in body["row_errors"][0]


# --- Human handoff reply ---


def test_handoff_reply_sends_whatsapp_with_correct_hospital_credentials(two_hospitals, fake_whatsapp_send):
    a = two_hospitals["a"]
    handoff = db.create_handoff_request(a["id"], "919876543210", reason="patient_requested")

    resp = client.post(
        f"/api/portal/handoffs/{handoff['id']}/reply", json={"text": "Reception here, how can we help?"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200
    assert len(fake_whatsapp_send) == 1
    call = fake_whatsapp_send[0]
    assert call["to"] == "919876543210"
    assert call["text"] == "Reception here, how can we help?"
    assert call["phone_number_id"] == "hospital-a-phone"
    assert call["access_token"] == "hospital-a-token"


def test_handoff_reply_does_not_auto_resolve(two_hospitals, fake_whatsapp_send):
    a = two_hospitals["a"]
    handoff = db.create_handoff_request(a["id"], "919876543210", reason="patient_requested")

    client.post(f"/api/portal/handoffs/{handoff['id']}/reply", json={"text": "still working on it"}, headers=_auth(a["token"]))

    still_open = db.get_handoff_requests(a["id"], status="open")
    assert any(h["id"] == handoff["id"] for h in still_open)


def test_handoff_reply_requires_nonempty_text(two_hospitals, fake_whatsapp_send):
    a = two_hospitals["a"]
    handoff = db.create_handoff_request(a["id"], "919876543210", reason="patient_requested")

    resp = client.post(f"/api/portal/handoffs/{handoff['id']}/reply", json={"text": "   "}, headers=_auth(a["token"]))
    assert resp.status_code == 400
    assert fake_whatsapp_send == []


# --- Cancel-with-message ---


def test_cancel_with_message_sends_whatsapp_after_commit(two_hospitals, fake_whatsapp_send):
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490009999")

    resp = client.post(
        f"/api/portal/bookings/{appt.id}/cancel", json={"message": "Your appointment has been cancelled."},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200

    cancelled = db.get_appointment(a["id"], appt.id)
    assert cancelled.status == db.STATUS_CANCELLED
    assert len(fake_whatsapp_send) == 1
    assert fake_whatsapp_send[0]["to"] == "5490009999"
    assert fake_whatsapp_send[0]["phone_number_id"] == "hospital-a-phone"


def test_cancel_without_message_sends_nothing(two_hospitals, fake_whatsapp_send):
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])

    resp = client.post(f"/api/portal/bookings/{appt.id}/cancel", json={"message": ""}, headers=_auth(a["token"]))
    assert resp.status_code == 200
    assert db.get_appointment(a["id"], appt.id).status == db.STATUS_CANCELLED
    assert fake_whatsapp_send == []


def test_cancel_survives_whatsapp_send_failure(two_hospitals, monkeypatch):
    """The cancellation itself already committed by the time the WhatsApp
    send is attempted -- a delivery failure (expired token, etc.) must not
    turn a successful cancel into a 500."""
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])

    async def failing_send_text(self, to, text):
        raise RuntimeError("simulated WhatsApp API failure")

    monkeypatch.setattr(portal_api.WhatsAppClient, "send_text", failing_send_text)

    resp = client.post(
        f"/api/portal/bookings/{appt.id}/cancel", json={"message": "cancelled"}, headers=_auth(a["token"])
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert db.get_appointment(a["id"], appt.id).status == db.STATUS_CANCELLED


def test_cancel_nonexistent_appointment_404s(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post("/api/portal/bookings/999999/cancel", headers=_auth(a["token"]))
    assert resp.status_code == 404


def test_cancel_routes_through_connector_not_directly_through_db(two_hospitals):
    """Audit follow-up: a Tier 2 hospital's cancel must fail loudly
    (ConnectorNotImplementedError -> 501), not silently "succeed" against
    the local DB row only while never touching that hospital's real system.
    Confirms portal_cancel_booking() no longer calls db.cancel_appointment()
    directly."""
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])

    h = db.get_hospital(a["id"])
    db.update_hospital(
        a["id"], name=h.name, whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token, app_secret=h.app_secret, timezone=h.timezone,
        welcome_message_text=h.welcome_message_text, reminder_offsets_hours=h.reminder_offsets_hours,
        reminder_template_name=h.reminder_template_name, data_tier="tier2",
        external_api_base_url="https://example.com/api", external_api_key="fake-key",
        portal_password_hash=h.portal_password_hash, enabled_features=h.enabled_features,
    )

    resp = client.post(f"/api/portal/bookings/{appt.id}/cancel", headers=_auth(a["token"]))
    assert resp.status_code == 501

    # Never touched -- Tier2Connector.cancel_booking() raises before any write.
    still_booked = db.get_appointment(a["id"], appt.id)
    assert still_booked.status == db.STATUS_BOOKED


# --- Reschedule-with-message (item 2) ---


def test_reschedule_with_message_sends_whatsapp_after_commit(two_hospitals, fake_whatsapp_send):
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490009999")
    new_slot = [s for s in db.get_slots(a["id"], a["doctor_id"]) if s["id"] != appt.scheduled_at.isoformat()][0]

    resp = client.post(
        f"/api/portal/bookings/{appt.id}/reschedule",
        json={
            "department_id": a["department_id"], "doctor_id": a["doctor_id"], "slot_id": new_slot["id"],
            "message": "Your appointment has been rescheduled.",
        },
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200, resp.text

    old = db.get_appointment(a["id"], appt.id)
    assert old.status == db.STATUS_RESCHEDULED
    new_appts = [x for x in db.get_all_appointments_for_hospital(a["id"]) if x.phone == "5490009999" and x.status == db.STATUS_BOOKED]
    assert len(new_appts) == 1
    assert new_appts[0].scheduled_at.isoformat() == new_slot["id"]

    assert len(fake_whatsapp_send) == 1
    assert fake_whatsapp_send[0]["to"] == "5490009999"
    assert fake_whatsapp_send[0]["phone_number_id"] == "hospital-a-phone"


def test_reschedule_without_message_sends_nothing(two_hospitals, fake_whatsapp_send):
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])
    new_slot = [s for s in db.get_slots(a["id"], a["doctor_id"]) if s["id"] != appt.scheduled_at.isoformat()][0]

    resp = client.post(
        f"/api/portal/bookings/{appt.id}/reschedule",
        json={"department_id": a["department_id"], "doctor_id": a["doctor_id"], "slot_id": new_slot["id"], "message": ""},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200
    assert fake_whatsapp_send == []


def test_reschedule_survives_whatsapp_send_failure(two_hospitals, monkeypatch):
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])
    new_slot = [s for s in db.get_slots(a["id"], a["doctor_id"]) if s["id"] != appt.scheduled_at.isoformat()][0]

    async def failing_send_text(self, to, text):
        raise RuntimeError("simulated WhatsApp API failure")

    monkeypatch.setattr(portal_api.WhatsAppClient, "send_text", failing_send_text)

    resp = client.post(
        f"/api/portal/bookings/{appt.id}/reschedule",
        json={"department_id": a["department_id"], "doctor_id": a["doctor_id"], "slot_id": new_slot["id"], "message": "moved"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200
    assert db.get_appointment(a["id"], appt.id).status == db.STATUS_RESCHEDULED


def test_reschedule_race_leaves_original_appointment_intact(two_hospitals):
    """Same guarantee as core/booking_flow.py's WhatsApp-side reschedule race
    test (tests/test_phase8_edge_cases.py) -- reuses the same
    connector.reschedule_booking() call, so it must have the same "new slot
    booked before the old one is touched" safety."""
    a = two_hospitals["a"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490001111")
    contested_slot = db.get_slots(a["id"], a["doctor_id"])[0]
    db.create_appointment(a["id"], "5490002222", a["department_id"], a["doctor_id"],
                           datetime.fromisoformat(contested_slot["id"]))

    resp = client.post(
        f"/api/portal/bookings/{appt.id}/reschedule",
        json={"department_id": a["department_id"], "doctor_id": a["doctor_id"], "slot_id": contested_slot["id"]},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 400
    assert "just taken" in resp.json()["errors"][0].lower()
    assert db.get_appointment(a["id"], appt.id).status == db.STATUS_BOOKED


def test_reschedule_cannot_target_other_hospitals_department_or_doctor(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    appt = _create_appointment(a["id"], a["doctor_id"], a["department_id"])
    resp = client.post(
        f"/api/portal/bookings/{appt.id}/reschedule",
        json={"department_id": b["department_id"], "doctor_id": b["doctor_id"], "slot_id": "2099-01-01T09:00:00"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 400
    assert db.get_appointment(a["id"], appt.id).status == db.STATUS_BOOKED


def test_reschedule_nonexistent_appointment_404s(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/bookings/999999/reschedule",
        json={"department_id": a["department_id"], "doctor_id": a["doctor_id"], "slot_id": "2099-01-01T09:00:00"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 404


# --- Doctor active/inactive toggle ---


def test_toggle_doctor_inactive_removes_from_bot_facing_get_doctors(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        f"/api/portal/doctors/{a['doctor_id']}/active", json={"is_active": False}, headers=_auth(a["token"])
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    bookable = db.get_doctors(a["id"], a["department_id"])
    assert all(d["id"] != a["doctor_id"] for d in bookable)

    # Management view still shows it (so staff can re-enable it).
    all_doctors = db.get_all_doctors_for_hospital(a["id"])
    assert any(d["id"] == a["doctor_id"] and d["is_active"] is False for d in all_doctors)


def test_toggle_doctor_back_active_restores_bookability(two_hospitals):
    a = two_hospitals["a"]
    client.post(f"/api/portal/doctors/{a['doctor_id']}/active", json={"is_active": False}, headers=_auth(a["token"]))
    client.post(f"/api/portal/doctors/{a['doctor_id']}/active", json={"is_active": True}, headers=_auth(a["token"]))

    bookable = db.get_doctors(a["id"], a["department_id"])
    assert any(d["id"] == a["doctor_id"] for d in bookable)


def test_toggle_nonexistent_doctor_404s(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post("/api/portal/doctors/totally-fake-id/active", json={"is_active": False}, headers=_auth(a["token"]))
    assert resp.status_code == 404


# --- Patients: list_patients / search_patients / get_recent_patients ---


def test_list_patients_search_filters_by_name_or_phone(two_hospitals):
    a = two_hospitals["a"]
    _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5491112223333", patient_name="Rahul Sharma")

    by_name = client.get("/api/portal/patients?search=Rahul", headers=_auth(a["token"]))
    assert {p["phone"] for p in by_name.json()["patients"]} == {"5491112223333"}

    by_phone = client.get("/api/portal/patients?search=1112223333", headers=_auth(a["token"]))
    assert {p["phone"] for p in by_phone.json()["patients"]} == {"5491112223333"}

    no_match = client.get("/api/portal/patients?search=nobody-like-this", headers=_auth(a["token"]))
    assert no_match.json()["patients"] == []


def test_recent_patients_on_dashboard_reflects_last_visit(two_hospitals):
    a = two_hospitals["a"]
    _create_appointment(a["id"], a["doctor_id"], a["department_id"], phone="5490001111", patient_name="Patient One")

    resp = client.get("/api/portal/dashboard", headers=_auth(a["token"]))
    recent = resp.json()["recent_patients"]
    assert any(p["phone"] == "5490001111" and p["name"] == "Patient One" and p["visit_count"] == 1 for p in recent)


# --- Auth basics (spot check across a representative sample of routes) ---


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/portal/dashboard"),
    ("GET", "/api/portal/doctors"),
    ("GET", "/api/portal/patients"),
    ("GET", "/api/portal/bookings"),
    ("GET", "/api/portal/handoffs"),
])
def test_get_routes_require_bearer_token(hospital_id, method, path):
    resp = client.get(path)
    assert resp.status_code == 401

    resp = client.get(path, headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


# --- Section 12.13: self-serve settings customization ---

def test_settings_get_includes_new_customization_fields_with_safe_defaults(two_hospitals):
    a = two_hospitals["a"]
    resp = client.get("/api/portal/settings", headers=_auth(a["token"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["feature_labels"] == {}
    assert data["closing_message_text"] == ""
    assert data["business_hours_text"] == ""
    assert data["default_language"] == "en"
    assert data["language_prompt_enabled"] is True
    assert data["session_timeout_minutes"] == 30
    assert "booking" in data["feature_default_labels"]


def test_settings_post_saves_and_get_reflects_new_fields(two_hospitals):
    a = two_hospitals["a"]
    payload = {
        "welcome_message_text": "Welcome!",
        "reminder_offsets_hours": "24",
        "reminder_template_name": "reminder",
        "feature_labels": {"booking": "Schedule a visit", "unknown_key": "ignored"},
        "closing_message_text": "Thank you for choosing us.",
        "business_hours_text": "Mon-Sat, 9am-8pm",
        "default_language": "hi",
        "language_prompt_enabled": False,
        "session_timeout_minutes": 45,
    }
    resp = client.post("/api/portal/settings", json=payload, headers=_auth(a["token"]))
    assert resp.status_code == 200

    get_resp = client.get("/api/portal/settings", headers=_auth(a["token"]))
    data = get_resp.json()
    assert data["feature_labels"] == {"booking": "Schedule a visit"}  # unrecognized key dropped
    assert data["closing_message_text"] == "Thank you for choosing us."
    assert data["business_hours_text"] == "Mon-Sat, 9am-8pm"
    assert data["default_language"] == "hi"
    assert data["language_prompt_enabled"] is False
    assert data["session_timeout_minutes"] == 45


def test_settings_post_rejects_invalid_default_language(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/settings",
        json={"welcome_message_text": "", "reminder_offsets_hours": "24", "reminder_template_name": "",
              "default_language": "fr"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 400


@pytest.mark.parametrize("bad_value", [0, 1, 121, 1000])
def test_settings_post_rejects_session_timeout_out_of_bounds(two_hospitals, bad_value):
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/settings",
        json={"welcome_message_text": "", "reminder_offsets_hours": "24", "reminder_template_name": "",
              "session_timeout_minutes": bad_value},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 400


def test_settings_post_accepts_2_minute_timeout(two_hospitals):
    """The lowered bound (was 5-120, now 2-120) -- a short timeout for
    testing/demoing the flow without a real 5+ minute wait."""
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/settings",
        json={"welcome_message_text": "", "reminder_offsets_hours": "24", "reminder_template_name": "",
              "session_timeout_minutes": 2},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200, resp.text
    get_resp = client.get("/api/portal/settings", headers=_auth(a["token"]))
    assert get_resp.json()["session_timeout_minutes"] == 2


def test_settings_customization_isolated_across_hospitals(two_hospitals):
    a, b = two_hospitals["a"], two_hospitals["b"]
    client.post(
        "/api/portal/settings",
        json={"welcome_message_text": "", "reminder_offsets_hours": "24", "reminder_template_name": "",
              "closing_message_text": "Hospital A only.", "default_language": "hi"},
        headers=_auth(a["token"]),
    )

    b_settings = client.get("/api/portal/settings", headers=_auth(b["token"])).json()
    assert b_settings["closing_message_text"] == ""
    assert b_settings["default_language"] == "en"


# --- Doctor break/quota fields + leave management (JSON equivalents of the
# old HTML-portal tests removed with portal.py's HTML routes -- see
# Spec.md Section 0) ---


def test_create_doctor_with_break_and_quota_fields(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/doctors",
        json={
            "department_id": a["department_id"], "name": "Dr. Portal Schedule",
            "working_days": ["Mon", "Wed"], "working_hours": ["09:00-12:00"],
            "slot_duration_minutes": "30", "breaks": ["10:00-10:30"],
            "max_bookings_per_slot": "1", "daily_booking_limit": "4",
        },
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200, resp.text
    doctor = resp.json()["doctor"]

    full = db.get_doctor_full(a["id"], doctor["id"])
    assert full["breaks"] == ["10:00-10:30"]
    assert full["daily_booking_limit"] == 4

    slots = db.get_slots(a["id"], doctor["id"])
    assert all(s["time"] != "10:00" for s in slots)


def test_create_doctor_quota_warning_shown_but_doctor_still_created(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        "/api/portal/doctors",
        json={
            "department_id": a["department_id"], "name": "Dr. Quota Warning",
            "working_days": ["Mon"], "working_hours": ["09:00-12:00"],
            "slot_duration_minutes": "30", "daily_booking_limit": "2",
            "online_quota": "2", "walkin_quota": "2",
        },
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["warnings"]  # non-blocking -- doctor is still created
    doctors = db.get_all_doctors_for_hospital(a["id"])
    assert any(d["name"] == "Dr. Quota Warning" for d in doctors)


def test_doctor_leave_add_list_and_delete(two_hospitals):
    a = two_hospitals["a"]
    resp = client.post(
        f"/api/portal/doctors/{a['doctor_id']}/leave",
        json={"date": "2027-03-01", "reason": "Vacation"},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["leave"] == {"date": "2027-03-01", "reason": "Vacation"}

    listed = client.get(f"/api/portal/doctors/{a['doctor_id']}/leave", headers=_auth(a["token"]))
    assert listed.status_code == 200
    assert [row["date"] for row in listed.json()["leave"]] == ["2027-03-01"]
    leave_id = listed.json()["leave"][0]["id"]

    deleted = client.post(
        f"/api/portal/doctors/{a['doctor_id']}/leave/{leave_id}/delete", headers=_auth(a["token"]),
    )
    assert deleted.status_code == 200
    assert db.get_doctor_leave(a["id"], a["doctor_id"]) == []
