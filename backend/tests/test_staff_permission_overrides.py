# tests/test_staff_permission_overrides.py
"""User-level permission overrides (see the approved plan at
.claude/plans/federated-enchanting-raven.md) -- a second, finer-grained
layer on top of role_permissions: an admin can grant/revoke one action on
one page for one specific staff member, which always wins over whatever
that staff member's role itself says. No dedicated RBAC test file existed
for the role-permission engine before this, so this file also exercises the
underlying role-default path incidentally."""
import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPER_ADMIN_JWT_SECRET", "test-super-admin-jwt-secret")

import db.repository as db  # noqa: E402
from db.repositories.hospitals import hash_portal_password  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from portal.permission_cache import invalidate  # noqa: E402
from portal.permissions import has_permission  # noqa: E402

client = TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _staff_login(email: str, password: str) -> dict:
    resp = client.post("/api/portal/staff/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _role_id(hospital_id: int, name: str) -> int:
    return next(r["id"] for r in db.list_roles(hospital_id) if r["name"].lower() == name.lower())


def _make_admin(hospital_id: int, email: str = "admin.overrides@example.com", password: str = "hunter22") -> str:
    db.create_staff_user(hospital_id, _role_id(hospital_id, "admin"), email, hash_portal_password(password), "Test Admin")
    return _staff_login(email, password)["access_token"]


def _make_doctor(hospital_id: int, name: str, email: str) -> int:
    doctor = db.create_doctor(hospital_id, "cardiology", name, working_days=["Mon"], working_hours=["09:00-12:00"])
    staff = db.create_staff_user(
        hospital_id, _role_id(hospital_id, "doctor"), email, hash_portal_password("hunter22"), name,
        doctor_id=doctor["id"],
    )
    return staff["id"]


def test_role_default_applies_when_no_override_exists(hospital_id):
    doctor_role_id = _role_id(hospital_id, "doctor")
    staff_id = _make_doctor(hospital_id, "Dr. No Override", "no.override@example.com")
    # Doctor role's own default (portal/permissions.py's seed data): delete
    # on appointments is False.
    assert has_permission(hospital_id, staff_id, doctor_role_id, "appointments", "delete") is False


def test_override_grants_extra_access_to_only_that_one_staff_member(hospital_id):
    doctor_role_id = _role_id(hospital_id, "doctor")
    priyanka_id = _make_doctor(hospital_id, "Dr. Priyanka", "priyanka@example.com")
    other_doctor_id = _make_doctor(hospital_id, "Dr. Other", "other.doctor@example.com")

    db.upsert_staff_override(hospital_id, priyanka_id, "appointments", None, None, True)
    from portal.permission_cache import invalidate_staff
    invalidate_staff(hospital_id, priyanka_id)

    assert has_permission(hospital_id, priyanka_id, doctor_role_id, "appointments", "delete") is True
    assert has_permission(hospital_id, other_doctor_id, doctor_role_id, "appointments", "delete") is False
    # The two untouched actions on that same page still fall through to the
    # role's own default (view+write both True for Doctor/appointments).
    assert has_permission(hospital_id, priyanka_id, doctor_role_id, "appointments", "view") is True


def test_override_can_explicitly_deny_something_the_role_grants(hospital_id):
    doctor_role_id = _role_id(hospital_id, "doctor")
    staff_id = _make_doctor(hospital_id, "Dr. Denied", "denied@example.com")
    assert has_permission(hospital_id, staff_id, doctor_role_id, "appointments", "view") is True

    db.upsert_staff_override(hospital_id, staff_id, "appointments", False, None, None)
    from portal.permission_cache import invalidate_staff
    invalidate_staff(hospital_id, staff_id)

    assert has_permission(hospital_id, staff_id, doctor_role_id, "appointments", "view") is False


def test_clearing_an_override_reverts_to_the_role_default_and_deletes_the_row(hospital_id):
    staff_id = _make_doctor(hospital_id, "Dr. Cleared", "cleared@example.com")
    db.upsert_staff_override(hospital_id, staff_id, "appointments", None, None, True)
    assert db.get_staff_overrides(hospital_id, staff_id) != []

    db.upsert_staff_override(hospital_id, staff_id, "appointments", None, None, None)
    assert db.get_staff_overrides(hospital_id, staff_id) == []


def test_get_role_users_returns_sparse_overrides_per_user(hospital_id):
    admin_token = _make_admin(hospital_id)
    doctor_role_id = _role_id(hospital_id, "doctor")
    priyanka_id = _make_doctor(hospital_id, "Dr. Priyanka Sparse", "priyanka.sparse@example.com")
    _make_doctor(hospital_id, "Dr. Untouched", "untouched@example.com")

    db.upsert_staff_override(hospital_id, priyanka_id, "appointments", None, None, True)

    resp = client.get(f"/api/portal/roles/{doctor_role_id}/users", headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    users = {u["staff_id"]: u for u in resp.json()["users"]}
    assert users[priyanka_id]["overrides"] == [{"page_key": "appointments", "view": None, "write": None, "delete": True}]
    untouched = next(u for sid, u in users.items() if sid != priyanka_id)
    assert untouched["overrides"] == []


def test_put_staff_permissions_sets_and_clears_an_override(hospital_id):
    admin_token = _make_admin(hospital_id)
    staff_id = _make_doctor(hospital_id, "Dr. Put", "put.overrides@example.com")
    doctor_role_id = _role_id(hospital_id, "doctor")

    resp = client.put(
        f"/api/portal/staff/{staff_id}/permissions",
        json={"updates": [{"page_key": "appointments", "delete": True}]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert has_permission(hospital_id, staff_id, doctor_role_id, "appointments", "delete") is True

    resp = client.put(
        f"/api/portal/staff/{staff_id}/permissions",
        json={"updates": [{"page_key": "appointments", "delete": None}]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert has_permission(hospital_id, staff_id, doctor_role_id, "appointments", "delete") is False


def test_put_staff_permissions_404s_for_a_staff_id_in_another_hospital(hospital_id, second_hospital_id):
    admin_token = _make_admin(hospital_id)
    other_admin_email = "other.hospital.admin@example.com"
    db.create_staff_user(
        second_hospital_id, _role_id(second_hospital_id, "admin"), other_admin_email,
        hash_portal_password("hunter22"), "Other Hospital Admin",
    )
    other_staff_id = _staff_login(other_admin_email, "hunter22")["staff"]["id"]

    resp = client.put(
        f"/api/portal/staff/{other_staff_id}/permissions",
        json={"updates": [{"page_key": "appointments", "delete": True}]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 404, resp.text


def test_put_staff_permissions_rejects_an_unrecognized_page(hospital_id):
    admin_token = _make_admin(hospital_id)
    staff_id = _make_doctor(hospital_id, "Dr. BadPage", "badpage@example.com")

    resp = client.put(
        f"/api/portal/staff/{staff_id}/permissions",
        json={"updates": [{"page_key": "not_a_real_page", "delete": True}]},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text


def test_attendance_and_check_in_out_default_to_every_role_except_admin(hospital_id):
    """Migration 20260914130000: unlike every other role_permissions
    backfill in this codebase (which apply to every role, admin included,
    e.g. holiday_application), these two pages deliberately give the seeded
    Admin role NO row at all -- confirmed with the user, an admin doesn't
    check themselves in/out day to day. Every other role gets view+write."""
    admin_role_id = _role_id(hospital_id, "admin")
    receptionist_role_id = _role_id(hospital_id, "receptionist")
    doctor_role_id = _role_id(hospital_id, "doctor")

    for page_key in ("attendance", "check_in_out"):
        assert has_permission(hospital_id, staff_id=-1, role_id=admin_role_id, page_key=page_key, action="view") is False
        assert has_permission(hospital_id, staff_id=-1, role_id=admin_role_id, page_key=page_key, action="write") is False
        assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key=page_key, action="view") is True
        assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key=page_key, action="write") is True
        assert has_permission(hospital_id, staff_id=-1, role_id=doctor_role_id, page_key=page_key, action="view") is True
        assert has_permission(hospital_id, staff_id=-1, role_id=doctor_role_id, page_key=page_key, action="write") is True


def test_daycare_and_diagnostic_appointments_start_cloned_from_appointments_then_diverge(hospital_id):
    """Migration 20260914140000: Doctor/Daycare/Lab & Diagnostic
    Appointments used to share one page_key ("appointments") -- confirmed
    with the user this was wrong, a role might reasonably get one category
    without the other two. The backfill CLONES each role's existing
    "appointments" permissions onto the two new page_keys, so nothing
    changes for any existing role on the day this ships (checked here via
    the seeded Receptionist role, which has real view+write on
    "appointments"); a later edit to just one of the three must NOT affect
    the other two, proving they're genuinely independent going forward."""
    receptionist_role_id = _role_id(hospital_id, "receptionist")
    # Defensive: tests/conftest.py's autouse _fresh_rbac_caches fixture only
    # resets the process-LOCAL cache between tests, not real Redis -- a
    # fresh hospital here can reuse a low integer id (id sequences reset
    # with the schema), so a still-TTL-alive Redis entry from an earlier,
    # separate pytest run that happened to mutate the SAME id could
    # otherwise leak in. Self-heals that rather than relying on it never
    # happening.
    invalidate(hospital_id)

    for page_key in ("appointments", "daycare_appointments", "diagnostic_appointments"):
        assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key=page_key, action="view") is True
        assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key=page_key, action="write") is True

    db.upsert_role_permissions(hospital_id, [
        {"role_id": receptionist_role_id, "page_key": "daycare_appointments", "can_view": False, "can_write": False, "can_delete": False},
    ])
    invalidate(hospital_id)

    assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key="daycare_appointments", action="view") is False
    # The other two are untouched by that one edit.
    assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key="appointments", action="view") is True
    assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key="diagnostic_appointments", action="view") is True

    # Cleanup: the fixture-reset _LOCAL_CACHE (tests/conftest.py's
    # _fresh_rbac_caches) doesn't touch real Redis, so without this, the
    # mutated matrix above would survive in Redis (5-minute TTL) past this
    # test and leak into a LATER, separate test run that reuses this same
    # hospital_id (fresh_test_db resets the id sequence every time).
    invalidate(hospital_id)


def test_report_review_and_analytics_default_permissions_differ_by_role(hospital_id):
    """Migration 20260914150000: unlike attendance/check_in_out (flat
    true/true for every non-admin role) or daycare/diagnostic appointments
    (cloned from an existing page), Report review and Report analytics are
    brand new with genuinely DIFFERENT per-role-kind defaults -- confirmed
    with the user. Admin gets both; Receptionist gets Report review
    (view+write) but only VIEW on Report analytics; Doctor gets Report
    review (view+write) but nothing at all on Report analytics."""
    admin_role_id = _role_id(hospital_id, "admin")
    receptionist_role_id = _role_id(hospital_id, "receptionist")
    doctor_role_id = _role_id(hospital_id, "doctor")

    for role_id in (admin_role_id, receptionist_role_id, doctor_role_id):
        assert has_permission(hospital_id, staff_id=-1, role_id=role_id, page_key="report-review", action="view") is True
        assert has_permission(hospital_id, staff_id=-1, role_id=role_id, page_key="report-review", action="write") is True

    assert has_permission(hospital_id, staff_id=-1, role_id=admin_role_id, page_key="report-analytics", action="view") is True
    assert has_permission(hospital_id, staff_id=-1, role_id=admin_role_id, page_key="report-analytics", action="write") is True
    assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key="report-analytics", action="view") is True
    assert has_permission(hospital_id, staff_id=-1, role_id=receptionist_role_id, page_key="report-analytics", action="write") is False
    assert has_permission(hospital_id, staff_id=-1, role_id=doctor_role_id, page_key="report-analytics", action="view") is False
    assert has_permission(hospital_id, staff_id=-1, role_id=doctor_role_id, page_key="report-analytics", action="write") is False
