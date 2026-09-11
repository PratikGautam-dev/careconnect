# tests/test_doctor_unified_login.py
"""
Doctor-frontend-restoration follow-up (Spec.md Section 0): the dedicated
/doctor/* frontend (login, dashboard, appointment detail, schedule) was
lost from `dev` when a concurrent branch (the unified staff/RBAC system,
docs/rbac-redis-plan.md) was merged in without it -- confirmed via git
history (merge-base(47401ab, HEAD) == 98556c3, my backend-only doctor-login
commit; the later frontend commit was never on the line that continued as
dev), not a deliberate deletion.

The unified system replaces the old standalone doctor login
(auth/doctor_session.py's DOCTOR_SECRET-signed token, /api/doctor/login,
both since deleted -- confirmed unused by any frontend UI) with a
staff_users row (role="doctor") authenticating through the SAME
/api/portal/staff/login every other staff role uses. portal/deps.py's
get_current_staff() + portal/routes/doctor_portal.py's _require_doctor()
now run this as the ONLY path (the dual-path fallback to the old doctor
token this file used to also prove was removed once the old path itself
was deleted) -- this file proves the isolation guarantee
tests/test_doctor_login.py (now deleted) originally established still
holds through the unified path: doctor_id is read only from the verified
identity, never a request parameter, so Dr. A's token can never reach Dr.
B's data.
"""
import os
from datetime import datetime, timedelta

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPER_ADMIN_JWT_SECRET", "test-super-admin-jwt-secret")

import pytest  # noqa: E402

import db.repository as db  # noqa: E402
from core.whatsapp import WhatsAppClient  # noqa: E402
from db.repositories.hospitals import hash_portal_password  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture
def fake_whatsapp_send(monkeypatch):
    """Same shape as test_portal_api.py's own fixture -- records every
    WhatsAppClient.send_text() call, no real HTTP call ever happens."""
    calls = []

    async def fake_send_text(self, to, text):
        calls.append({"to": to, "text": text})

    monkeypatch.setattr(WhatsAppClient, "send_text", fake_send_text)
    return calls


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_doctor_staff_user(hospital_id: int, name: str, email: str, password: str = "hunter22") -> str:
    """Creates a doctor row + a staff_users login for it, unified-system
    style -- doctor_id is required on a role="doctor" row (the DB's own
    ck_staff_users_doctor_role_pairing CHECK enforces this), unlike the old
    doctors.email/password_hash path which lived on the doctor row itself."""
    doctor = db.create_doctor(
        hospital_id, "cardiology", name,
        working_days=["Mon", "Tue", "Wed", "Thu", "Fri"], working_hours=["09:00-12:00"],
    )
    db.create_staff_user(hospital_id, "doctor", email, hash_portal_password(password), name, doctor_id=doctor["id"])
    return doctor["id"]


def _staff_login(email: str, password: str) -> dict:
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


_book_call_count = 0


def _book(hospital_id: int, doctor_id: str, phone: str) -> int:
    # A directly-computed near-future timestamp, not db.get_slots()[0] --
    # slot generation's first available slot can legitimately fall on
    # tomorrow depending on the time of day the suite happens to run
    # (generate_slots_for_doctor()'s own margin logic), which would make
    # this booking miss get_doctor_appointments_today()'s "today" window
    # through no fault of the isolation logic under test.
    # create_appointment() doesn't require the slot to pre-exist in
    # doctor_slots, only that capacity/quota checks pass.
    #
    # An incrementing per-call minute offset (not just "+30 minutes,
    # rounded to the minute") -- two calls for the SAME doctor within the
    # same test, close enough together to land in the same real-world
    # minute (routine at test speed), would otherwise collide on the
    # partial unique booked-slot index and fail with a spurious
    # IntegrityError that has nothing to do with whatever isolation
    # property the test is actually checking.
    global _book_call_count
    _book_call_count += 1
    scheduled_at = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=30 + _book_call_count)
    appointment = db.create_appointment(hospital_id, phone, "cardiology", doctor_id, scheduled_at)
    return appointment.id


def test_unified_staff_login_for_a_doctor_role_reports_role_doctor(hospital_id):
    _make_doctor_staff_user(hospital_id, "Dr. Unified One", "unified.one@example.com")
    body = _staff_login("unified.one@example.com", "hunter22")
    assert body["staff"]["role"] == "doctor"
    assert body["staff"]["hospital_id"] == hospital_id


def test_unified_login_token_correctly_scopes_doctor_portal_routes(hospital_id):
    """The actual unified-login proof: a staff JWT authenticates
    successfully against /api/doctor/* -- confirming _require_doctor()'s
    get_current_staff() check works, not just that it compiles."""
    doctor_id = _make_doctor_staff_user(hospital_id, "Dr. Unified Two", "unified.two@example.com")
    _book(hospital_id, doctor_id, "5490003333")
    token = _staff_login("unified.two@example.com", "hunter22")["access_token"]

    resp = client.get("/api/doctor/dashboard", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["today_appointments"]) == 1


def test_unified_login_doctor_a_still_cannot_reach_doctor_bs_appointments(hospital_id):
    """Same isolation guarantee as tests/test_doctor_login.py's own
    cross-doctor test, proven again through the NEW login path. The
    per-appointment routes (detail/attendance/notes) this used to probe
    directly were removed as duplicates of the now-scoped /api/portal/
    bookings(+{id}) -- see test_portal_doctor_scoping.py for that proof;
    what's left here is that /api/doctor/dashboard's own doctor_id-scoped
    query never leaks doctor B's appointment into doctor A's."""
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Unified A", "unified.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. Unified B", "unified.b@example.com", "pwB")
    _book(hospital_id, doctor_a, "5490004444")
    appointment_b_id = _book(hospital_id, doctor_b, "5490005555")

    token_a = _staff_login("unified.a@example.com", "pwA")["access_token"]

    dashboard_resp = client.get("/api/doctor/dashboard", headers=_auth(token_a))
    assert dashboard_resp.status_code == 200
    seen_ids = {a["id"] for a in dashboard_resp.json()["today_appointments"]}
    assert appointment_b_id not in seen_ids


def test_unified_login_doctor_cannot_authenticate_against_shared_staff_portal_routes_as_someone_else(hospital_id):
    """A doctor's own staff JWT is a real, valid staff credential -- unlike
    the old DOCTOR_SECRET token (which the shared /api/portal/* routes
    reject outright, different signing secret entirely), this one DOES
    verify as a real StaffPrincipal. The isolation that matters here is
    architectural, not cryptographic: this proves the doctor role only ever
    reaches the doctor-scoped repository query (get_doctor_appointments_today,
    filtered by doctor_id), confirming there is no path from this same valid
    token to db.get_all_appointments_for_hospital() (the shared, unscoped
    query /api/portal/bookings uses) -- the frontend guard
    (usePortalGuard/useDoctorGuard's role redirect) is what keeps a doctor
    out of that page in the product; this test is the backend-side half of
    that guarantee, confirming the doctor-scoped route never widens beyond
    its own doctor_id regardless of which valid staff role calls it."""
    doctor_id = _make_doctor_staff_user(hospital_id, "Dr. Unified Scope", "unified.scope@example.com")
    _book(hospital_id, doctor_id, "5490006666")
    other_doctor = db.create_doctor(hospital_id, "cardiology", "Dr. Other Unscoped")
    _book(hospital_id, other_doctor["id"], "5490007777")

    token = _staff_login("unified.scope@example.com", "hunter22")["access_token"]
    resp = client.get("/api/doctor/dashboard", headers=_auth(token))
    assert resp.status_code == 200
    doctor_ids_seen = {db.get_appointment(hospital_id, a["id"]).doctor_id for a in resp.json()["today_appointments"]}
    assert doctor_ids_seen == {doctor_id}


# --- Doctor-portal follow-up (Spec.md Section 0): dashboard/calendar get
# the same isolation proof as every other /api/doctor/* route above: a
# doctor never sees another doctor's numbers or appointments. (The old
# full-appointments-list, full-patients-list, and patient-detail routes
# this section used to also cover were removed as duplicates of the now
# doctor_id-scoped /api/portal/bookings and /api/portal/patients(+{id}) --
# see test_portal_doctor_scoping.py for those isolation proofs instead.) ---

def test_doctor_dashboard_stats_are_scoped_to_this_doctor_only(hospital_id):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Dash A", "dash.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. Dash B", "dash.b@example.com", "pwB")
    _book(hospital_id, doctor_a, "5490008881")
    _book(hospital_id, doctor_b, "5490008882")
    _book(hospital_id, doctor_b, "5490008883")

    token_a = _staff_login("dash.a@example.com", "pwA")["access_token"]
    resp = client.get("/api/doctor/dashboard", headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["doctor"]["id"] == doctor_a
    assert body["stats"]["today_appointments"] == 1  # not 3 (A's own + both of B's)
    assert len(body["today_appointments"]) == 1


# --- Doctor-portal follow-up: dashboard trend/donut, the patient-detail
# page, and the "running late" bulk-delay feature. ---

def test_doctor_dashboard_weekly_counts_and_recent_are_scoped(hospital_id):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Trend A", "trend.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. Trend B", "trend.b@example.com", "pwB")
    appt_a = _book(hospital_id, doctor_a, "5490009991")
    _book(hospital_id, doctor_b, "5490009992")
    db.mark_attendance(hospital_id, appt_a, True)

    token_a = _staff_login("trend.a@example.com", "pwA")["access_token"]
    resp = client.get("/api/doctor/dashboard", headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sum(p["count"] for p in body["weekly_counts"]) == 1  # only A's own booking
    assert len(body["recent_appointments"]) == 1


def test_doctor_appointments_calendar_is_scoped_to_this_doctor_and_month(hospital_id):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Cal A", "cal.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. Cal B", "cal.b@example.com", "pwB")
    appt_a = _book(hospital_id, doctor_a, "5490009995")
    _book(hospital_id, doctor_b, "5490009996")

    token_a = _staff_login("cal.a@example.com", "pwA")["access_token"]
    now = datetime.now()
    resp = client.get(
        f"/api/doctor/appointments/calendar?year={now.year}&month={now.month}", headers=_auth(token_a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [a["id"] for a in body["appointments"]] == [appt_a]

    # A different month has nothing for this doctor.
    other_month = 1 if now.month != 1 else 2
    resp = client.get(
        f"/api/doctor/appointments/calendar?year={now.year}&month={other_month}", headers=_auth(token_a),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["appointments"] == []


def test_running_late_shifts_only_this_doctors_remaining_today_appointments_and_notifies(hospital_id, fake_whatsapp_send):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Late A", "late.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. Late B", "late.b@example.com", "pwB")
    appt_a = _book(hospital_id, doctor_a, "5490009995")
    appt_b = _book(hospital_id, doctor_b, "5490009996")
    original_time_a = db.get_appointment(hospital_id, appt_a).scheduled_at
    original_time_b = db.get_appointment(hospital_id, appt_b).scheduled_at

    token_a = _staff_login("late.a@example.com", "pwA")["access_token"]
    resp = client.post("/api/doctor/appointments/delay", json={"minutes": 20}, headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["notified"] == 1
    assert [a["id"] for a in body["appointments"]] == [appt_a]

    shifted = db.get_appointment(hospital_id, appt_a)
    assert shifted.scheduled_at == original_time_a + timedelta(minutes=20)
    untouched = db.get_appointment(hospital_id, appt_b)
    assert untouched.scheduled_at == original_time_b  # doctor B's own appointment is completely unaffected
    assert len(fake_whatsapp_send) == 1
    assert fake_whatsapp_send[0]["to"] == "5490009995"


def test_running_late_does_not_shift_a_past_or_already_attended_appointment(hospital_id, fake_whatsapp_send):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Late C", "late.c@example.com", "pwC")
    appt_past = _book(hospital_id, doctor_a, "5490009997")
    # Backdate it to earlier today so it's no longer "remaining."
    db.get_connection().execute(
        "UPDATE appointments SET scheduled_at = ? WHERE id = ?",
        ((datetime.now() - timedelta(minutes=5)).isoformat(), appt_past),
    )
    appt_attended = _book(hospital_id, doctor_a, "5490009998")
    db.mark_attendance(hospital_id, appt_attended, True)

    token_a = _staff_login("late.c@example.com", "pwC")["access_token"]
    resp = client.post("/api/doctor/appointments/delay", json={"minutes": 15}, headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    assert resp.json()["notified"] == 0
    assert fake_whatsapp_send == []


def test_running_late_validates_minutes(hospital_id):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Late D", "late.d@example.com", "pwD")
    token_a = _staff_login("late.d@example.com", "pwD")["access_token"]
    resp = client.post("/api/doctor/appointments/delay", json={"minutes": 0}, headers=_auth(token_a))
    assert resp.status_code == 400
    resp = client.post("/api/doctor/appointments/delay", json={"minutes": 999}, headers=_auth(token_a))
    assert resp.status_code == 400
    resp = client.post("/api/doctor/appointments/delay", json={}, headers=_auth(token_a))
    assert resp.status_code == 400
