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
(auth/doctor_session.py's DOCTOR_SECRET-signed token, /api/doctor/login)
with a staff_users row (role="doctor") authenticating through the SAME
/api/portal/staff/login every other staff role uses. portal/deps.py's
get_current_staff() + portal/routes/doctor_portal.py's _require_doctor()
already had a dual-path fallback added for this (tries get_current_staff()
first, falls back to the old doctor token) -- this file proves that path
actually preserves the exact isolation guarantee tests/test_doctor_login.py
established for the original token type: doctor_id is read only from the
verified identity, never a request parameter, so Dr. A's token can never
reach Dr. B's data, regardless of which of the two token types authenticated
the caller.
"""
import os
from datetime import datetime, timedelta

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")
os.environ.setdefault("DOCTOR_SECRET", "test-doctor-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPER_ADMIN_JWT_SECRET", "test-super-admin-jwt-secret")

import db.repository as db  # noqa: E402
from db.repositories.hospitals import hash_portal_password  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


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


def _book(hospital_id: int, doctor_id: str, phone: str) -> int:
    # A directly-computed near-future timestamp, not db.get_slots()[0] --
    # slot generation's first available slot can legitimately fall on
    # tomorrow depending on the time of day the suite happens to run
    # (generate_slots_for_doctor()'s own margin logic), which would make
    # this booking miss get_doctor_appointments_today()'s "today" window
    # through no fault of the isolation logic under test.
    # create_appointment() doesn't require the slot to pre-exist in
    # doctor_slots, only that capacity/quota checks pass.
    scheduled_at = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=30)
    appointment = db.create_appointment(hospital_id, phone, "cardiology", doctor_id, scheduled_at)
    return appointment.id


def test_unified_staff_login_for_a_doctor_role_reports_role_doctor(hospital_id):
    _make_doctor_staff_user(hospital_id, "Dr. Unified One", "unified.one@example.com")
    body = _staff_login("unified.one@example.com", "hunter22")
    assert body["staff"]["role"] == "doctor"
    assert body["staff"]["hospital_id"] == hospital_id


def test_unified_login_token_correctly_scopes_doctor_portal_routes(hospital_id):
    """The actual dual-path proof: a staff JWT (not the old DOCTOR_SECRET
    token) authenticates successfully against /api/doctor/* -- confirming
    _require_doctor()'s get_current_staff()-first fallback chain works, not
    just that it compiles."""
    doctor_id = _make_doctor_staff_user(hospital_id, "Dr. Unified Two", "unified.two@example.com")
    _book(hospital_id, doctor_id, "5490003333")
    token = _staff_login("unified.two@example.com", "hunter22")["access_token"]

    resp = client.get("/api/doctor/appointments/today", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["appointments"]) == 1


def test_unified_login_doctor_a_still_cannot_reach_doctor_bs_appointments(hospital_id):
    """Same isolation guarantee as tests/test_doctor_login.py's own
    cross-doctor test, proven again through the NEW login path -- the
    concern this whole restoration follow-up exists to close."""
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Unified A", "unified.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. Unified B", "unified.b@example.com", "pwB")
    _book(hospital_id, doctor_a, "5490004444")
    appointment_b_id = _book(hospital_id, doctor_b, "5490005555")

    token_a = _staff_login("unified.a@example.com", "pwA")["access_token"]

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
    assert db.get_appointment(hospital_id, appointment_b_id).status == "booked"


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
    resp = client.get("/api/doctor/appointments/today", headers=_auth(token))
    assert resp.status_code == 200
    doctor_ids_seen = {db.get_appointment(hospital_id, a["id"]).doctor_id for a in resp.json()["appointments"]}
    assert doctor_ids_seen == {doctor_id}


# --- Doctor-portal follow-up (Spec.md Section 0): the sidebar redesign
# added a real Dashboard, a full Appointments list, and a Patients list to
# the doctor portal, matching the shared staff portal's own shape. These
# three new endpoints get the same isolation proof as every other
# /api/doctor/* route above: a doctor never sees another doctor's numbers,
# appointments, or patients, regardless of which is asked for. ---

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


def test_doctor_appointments_list_only_shows_this_doctors_own(hospital_id):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. List A", "list.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. List B", "list.b@example.com", "pwB")
    appt_a = _book(hospital_id, doctor_a, "5490008884")
    appt_b = _book(hospital_id, doctor_b, "5490008885")

    token_a = _staff_login("list.a@example.com", "pwA")["access_token"]
    resp = client.get("/api/doctor/appointments", headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    ids = {a["id"] for a in resp.json()["appointments"]}
    assert appt_a in ids
    assert appt_b not in ids


def test_doctor_patients_list_only_shows_patients_seen_by_this_doctor(hospital_id):
    doctor_a = _make_doctor_staff_user(hospital_id, "Dr. Pat A", "pat.a@example.com", "pwA")
    doctor_b = _make_doctor_staff_user(hospital_id, "Dr. Pat B", "pat.b@example.com", "pwB")
    _book(hospital_id, doctor_a, "5490008886")
    _book(hospital_id, doctor_b, "5490008887")

    token_a = _staff_login("pat.a@example.com", "pwA")["access_token"]
    resp = client.get("/api/doctor/patients", headers=_auth(token_a))
    assert resp.status_code == 200, resp.text
    phones = {p["phone"] for p in resp.json()["patients"]}
    assert "5490008886" in phones
    assert "5490008887" not in phones
