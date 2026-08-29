# tests/test_doctor_login.py
"""
Dedicated doctor login (Spec.md Section 0's doctor-portal build) --
auth/doctor_session.py, portal/routes/doctor_auth.py,
portal/routes/doctor_portal.py, and portal/routes/doctors.py's admin-issued
credential route. The central concern this file exists to prove: a doctor's
own valid token can NEVER be used to reach another doctor's data at the
same hospital, or a doctor at a different hospital -- every route reads
doctor_id ONLY from the verified token, never from a request parameter.
"""
import os
from datetime import datetime

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")
os.environ.setdefault("DOCTOR_SECRET", "test-doctor-secret")

import db.repository as db  # noqa: E402
from auth.doctor_session import issue_doctor_session, verify_doctor_session  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def _set_hospital_password(hospital_id_val: int, password: str) -> None:
    h = db.get_hospital(hospital_id_val)
    db.update_hospital(
        hospital_id_val,
        name=h.name,
        whatsapp_phone_number_id=h.whatsapp_phone_number_id,
        access_token=h.access_token,
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
        tenant_type=h.tenant_type,
        admin_capabilities=h.admin_capabilities,
    )


def _login(hospital_id_val: int, password: str = "test-portal-password") -> str:
    _set_hospital_password(hospital_id_val, password)
    resp = client.post("/api/portal/login", json={"password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_doctor_with_login(hospital_id: int, name: str, email: str, staff_token: str, password: str = "hunter22"):
    doctor = db.create_doctor(
        hospital_id, "cardiology", name,
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-12:00"],
    )
    resp = client.post(
        f"/api/portal/doctors/{doctor['id']}/login-credentials",
        json={"email": email, "password": password},
        headers=_auth(staff_token),
    )
    assert resp.status_code == 200, resp.text
    return doctor["id"]


def _book(hospital_id: int, doctor_id: str, phone: str) -> int:
    slot = db.get_slots(hospital_id, doctor_id)[0]
    scheduled_at = datetime.fromisoformat(slot["id"])
    appointment = db.create_appointment(hospital_id, phone, "cardiology", doctor_id, scheduled_at)
    return appointment.id


# --- Login itself ---

def test_doctor_login_succeeds_with_correct_credentials(hospital_id):
    staff_token = _login(hospital_id)
    doctor_id = _make_doctor_with_login(hospital_id, "Dr. Login Test", "login.test@example.com", staff_token)
    resp = client.post("/api/doctor/login", json={"email": "login.test@example.com", "password": "hunter22"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["doctor"]["id"] == doctor_id
    assert verify_doctor_session(body["token"]) == (hospital_id, doctor_id)


def test_doctor_login_rejects_wrong_password(hospital_id):
    staff_token = _login(hospital_id)
    _make_doctor_with_login(hospital_id, "Dr. Wrong Pw", "wrongpw@example.com", staff_token)
    resp = client.post("/api/doctor/login", json={"email": "wrongpw@example.com", "password": "not-it"})
    assert resp.status_code == 401


def test_doctor_login_rejects_unknown_email(hospital_id):
    resp = client.post("/api/doctor/login", json={"email": "nobody@example.com", "password": "x"})
    assert resp.status_code == 401


def test_doctor_with_no_credentials_set_cannot_log_in(hospital_id):
    """A doctor row with email IS NULL (the normal, pre-this-feature state
    for every existing doctor) has no login at all -- confirms this is
    genuinely additive/opt-in, not something every doctor is silently
    enrolled into."""
    db.create_doctor(hospital_id, "cardiology", "Dr. No Login")
    resp = client.post("/api/doctor/login", json={"email": "no.login@example.com", "password": "anything"})
    assert resp.status_code == 401


def test_login_requires_both_fields(hospital_id):
    resp = client.post("/api/doctor/login", json={"email": "", "password": ""})
    assert resp.status_code == 400


def test_doctor_token_rejected_by_shared_staff_portal_routes(hospital_id):
    """A doctor token is signed with DOCTOR_SECRET, not PORTAL_SECRET -- it
    must never be accepted by an existing /api/portal/* route."""
    staff_token = _login(hospital_id)
    doctor_id = _make_doctor_with_login(hospital_id, "Dr. Cross Auth", "crossauth@example.com", staff_token)
    login_resp = client.post("/api/doctor/login", json={"email": "crossauth@example.com", "password": "hunter22"})
    doctor_token = login_resp.json()["token"]
    resp = client.get("/api/portal/doctors", headers=_auth(doctor_token))
    assert resp.status_code == 401


def test_staff_token_rejected_by_doctor_portal_routes(hospital_id):
    staff_token = _login(hospital_id)
    resp = client.get("/api/doctor/appointments/today", headers=_auth(staff_token))
    assert resp.status_code == 401


def test_expired_or_tampered_doctor_token_rejected(hospital_id):
    doctor = db.create_doctor(hospital_id, "cardiology", "Dr. Tamper Test")
    token = issue_doctor_session(hospital_id, doctor["id"])
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    resp = client.get("/api/doctor/appointments/today", headers=_auth(tampered))
    assert resp.status_code == 401
    resp = client.get("/api/doctor/appointments/today", headers=_auth(""))
    assert resp.status_code == 401


# --- The actual isolation guarantee ---

def test_doctor_a_cannot_see_doctor_bs_appointments(hospital_id):
    staff_token = _login(hospital_id)
    doctor_a = _make_doctor_with_login(hospital_id, "Dr. A", "dr.a@example.com", staff_token, "pwA-secret")
    doctor_b = _make_doctor_with_login(hospital_id, "Dr. B", "dr.b@example.com", staff_token, "pwB-secret")
    _book(hospital_id, doctor_a, "5490001111")
    appointment_b_id = _book(hospital_id, doctor_b, "5490002222")

    token_a = client.post("/api/doctor/login", json={"email": "dr.a@example.com", "password": "pwA-secret"}).json()["token"]

    today_resp = client.get("/api/doctor/appointments/today", headers=_auth(token_a))
    assert today_resp.status_code == 200
    seen_ids = {a["id"] for a in today_resp.json()["appointments"]}
    assert appointment_b_id not in seen_ids

    detail_resp = client.get(f"/api/doctor/appointments/{appointment_b_id}", headers=_auth(token_a))
    assert detail_resp.status_code == 404

    attendance_resp = client.post(
        f"/api/doctor/appointments/{appointment_b_id}/attendance", json={"attended": True}, headers=_auth(token_a),
    )
    assert attendance_resp.status_code == 404
    # Confirm the attempt was actually rejected, not silently applied.
    assert db.get_appointment(hospital_id, appointment_b_id).status == "booked"

    note_resp = client.post(
        f"/api/doctor/appointments/{appointment_b_id}/notes", json={"note_text": "should not land"}, headers=_auth(token_a),
    )
    assert note_resp.status_code == 404


def test_doctor_a_cannot_touch_doctor_bs_schedule_or_leave(hospital_id):
    staff_token = _login(hospital_id)
    doctor_a = _make_doctor_with_login(hospital_id, "Dr. Sched A", "sched.a@example.com", staff_token, "pwA")
    doctor_b = _make_doctor_with_login(hospital_id, "Dr. Sched B", "sched.b@example.com", staff_token, "pwB")
    db.create_doctor_leave(hospital_id, doctor_b, "2027-03-01", "Conference")
    leave_b_id = db.get_doctor_leave(hospital_id, doctor_b)[0]["id"]

    token_a = client.post("/api/doctor/login", json={"email": "sched.a@example.com", "password": "pwA"}).json()["token"]

    # Dr. A's own schedule route only ever reads/writes Dr. A's own row --
    # there is no parameter through which Dr. B's doctor_id could be supplied.
    sched_resp = client.get("/api/doctor/schedule", headers=_auth(token_a))
    assert sched_resp.status_code == 200
    assert sched_resp.json()["doctor"]["id"] == doctor_a

    update_resp = client.post(
        "/api/doctor/schedule", json={"working_hours": ["08:00-10:00"]}, headers=_auth(token_a),
    )
    assert update_resp.status_code == 200
    assert db.get_doctor_full(hospital_id, doctor_b)["working_hours"] == ["09:00-12:00"]  # untouched

    # Dr. B's own leave row, referenced by id alone -- Dr. A's token still
    # can't delete it, since delete_doctor_leave() is scoped by (hospital_id,
    # doctor_id) and doctor_id here is Dr. A's, from Dr. A's own token.
    delete_resp = client.post(f"/api/doctor/leave/{leave_b_id}/delete", headers=_auth(token_a))
    assert delete_resp.status_code == 404
    assert len(db.get_doctor_leave(hospital_id, doctor_b)) == 1


def test_doctor_login_isolated_across_hospitals(hospital_id, second_hospital_id):
    staff_token_1 = _login(hospital_id)
    doctor_1 = _make_doctor_with_login(hospital_id, "Dr. Tenant One", "tenant1@example.com", staff_token_1, "pw1")

    # A doctor token minted for hospital #1 must not resolve against hospital #2's data.
    token_1 = client.post("/api/doctor/login", json={"email": "tenant1@example.com", "password": "pw1"}).json()["token"]
    me_resp = client.get("/api/doctor/me", headers=_auth(token_1))
    assert me_resp.status_code == 200
    assert me_resp.json()["hospital"]["id"] == hospital_id


def test_login_credentials_email_must_be_globally_unique(hospital_id):
    """ux_doctors_email is a global unique index, not per-hospital -- a
    second doctor (even at the same hospital) can't claim an email already
    in use by another doctor."""
    staff_token = _login(hospital_id)
    doctor_1 = db.create_doctor(hospital_id, "cardiology", "Dr. Dup One")
    doctor_2 = db.create_doctor(hospital_id, "cardiology", "Dr. Dup Two")
    resp1 = client.post(
        f"/api/portal/doctors/{doctor_1['id']}/login-credentials",
        json={"email": "dupe@example.com", "password": "pw"}, headers=_auth(staff_token),
    )
    assert resp1.status_code == 200
    resp2 = client.post(
        f"/api/portal/doctors/{doctor_2['id']}/login-credentials",
        json={"email": "dupe@example.com", "password": "pw2"}, headers=_auth(staff_token),
    )
    assert resp2.status_code == 409

    resp3 = client.post(
        f"/api/portal/doctors/{doctor_1['id']}/login-credentials",
        json={"email": "dupe@example.com", "password": "pw3"}, headers=_auth(staff_token),
    )
    # Same doctor re-using their own email is a no-op re-set, not a conflict.
    assert resp3.status_code == 200


def test_revoking_login_credentials_blocks_future_logins(hospital_id):
    staff_token = _login(hospital_id)
    doctor_id = _make_doctor_with_login(hospital_id, "Dr. Revoke Test", "revoke.test@example.com", staff_token)
    revoke_resp = client.post(
        f"/api/portal/doctors/{doctor_id}/login-credentials/revoke", headers=_auth(staff_token),
    )
    assert revoke_resp.status_code == 200
    resp = client.post("/api/doctor/login", json={"email": "revoke.test@example.com", "password": "hunter22"})
    assert resp.status_code == 401


def test_inactive_doctor_cannot_log_in_even_with_correct_password(hospital_id):
    staff_token = _login(hospital_id)
    doctor_id = _make_doctor_with_login(hospital_id, "Dr. Inactive Test", "inactive.test@example.com", staff_token)
    client.post(f"/api/portal/doctors/{doctor_id}/active", json={"is_active": False}, headers=_auth(staff_token))
    resp = client.post("/api/doctor/login", json={"email": "inactive.test@example.com", "password": "hunter22"})
    assert resp.status_code == 401
