# tests/test_capability_gating.py
"""
Tenant-type-driven capability gating (tenant-capability-gating-plan.md):
hospitals keep full staff-portal admin capability; clinics get a reduced
management surface (no doctor/department management) -- config-driven per
tenant (hospitals.tenant_type/admin_capabilities), defaulted by tenant type,
editable later by the platform admin, with zero per-tenant-type conditional
logic in feature code (portal/capabilities.py's get_capabilities()/
has_capability() + portal/deps.py's require_capability() are the ONE place
this is decided).
"""
import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from datetime import datetime  # noqa: E402

import db.repository as db  # noqa: E402
from main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from portal.capabilities import (  # noqa: E402
    ALL_CAPABILITIES, DEFAULT_CAPABILITIES_BY_TYPE, get_capabilities, has_capability,
)

client = TestClient(app)

TENANTS_ADMIN_SECRET = "test-tenants-admin-secret"
_TENANTS_HEADERS = {"X-Admin-Secret": TENANTS_ADMIN_SECRET}


_UNSET = object()


def _set_hospital(hospital_id: int, *, password: str, tenant_type=_UNSET, admin_capabilities=_UNSET) -> None:
    """Same pattern as tests/test_portal_api.py's own _set_hospital_creds --
    a real portal password (so /api/portal/login works) plus, here, an
    explicit tenant_type/admin_capabilities override for the scenario under
    test. Uses a real sentinel (not None) to distinguish "not passed, keep
    the hospital's current value" from "explicitly passed None" -- matching
    db.update_hospital()'s own actual contract: None IS a real, writable
    value there (it writes admin_capabilities back to NULL), not a "keep
    current" marker -- that inheritance behavior only exists in callers
    like admin/tenants_api.py that explicitly implement it via
    model_fields_set. An earlier version of this helper conflated the two
    and silently kept a stale non-NULL admin_capabilities in place across a
    tenant_type change, making two "clinic should be blocked" tests below
    falsely pass with 200 instead of 403 -- caught by actually running them,
    not by inspection."""
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id,
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
        tenant_type=h.tenant_type if tenant_type is _UNSET else tenant_type,
        admin_capabilities=h.admin_capabilities if admin_capabilities is _UNSET else admin_capabilities,
    )


def _login(password: str) -> str:
    resp = client.post("/api/portal/login", json={"password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Unit: get_capabilities()/has_capability() ---

class _FakeHospital:
    def __init__(self, tenant_type: str, admin_capabilities):
        self.tenant_type = tenant_type
        self.admin_capabilities = admin_capabilities


def test_get_capabilities_falls_back_to_hospital_default_when_unset():
    h = _FakeHospital("hospital", None)
    assert get_capabilities(h) == DEFAULT_CAPABILITIES_BY_TYPE["hospital"]
    assert has_capability(h, "manage_doctors") is True


def test_get_capabilities_falls_back_to_clinic_default_when_unset():
    h = _FakeHospital("clinic", None)
    assert get_capabilities(h) == DEFAULT_CAPABILITIES_BY_TYPE["clinic"]
    assert has_capability(h, "manage_doctors") is False
    assert has_capability(h, "manage_bookings") is True


def test_get_capabilities_explicit_override_wins_over_type_default():
    """A hospital-type tenant with an explicit, reduced admin_capabilities
    override behaves like the override, not like its type's default --
    confirms admin_capabilities (when set) is authoritative either
    direction, not just a way to grant MORE than the type default."""
    h = _FakeHospital("hospital", ["manage_bookings"])
    assert get_capabilities(h) == {"manage_bookings"}
    assert has_capability(h, "manage_doctors") is False


def test_get_capabilities_explicit_empty_list_means_zero_capabilities():
    h = _FakeHospital("clinic", [])
    assert get_capabilities(h) == set()
    assert has_capability(h, "manage_bookings") is False


def test_get_capabilities_ignores_unrecognized_stray_values():
    """A stray/typo'd capability string in the stored column (e.g. from a
    future rename) is silently dropped, not treated as a real capability --
    same "never trust a stored value beyond the currently-known set"
    discipline enabled_features validation already follows."""
    h = _FakeHospital("hospital", ["manage_bookings", "totally_made_up"])
    assert get_capabilities(h) == {"manage_bookings"}


def test_all_capabilities_covers_every_default():
    for capabilities in DEFAULT_CAPABILITIES_BY_TYPE.values():
        assert capabilities <= ALL_CAPABILITIES


# --- Integration: require_capability() gating real /api/portal/doctors routes ---

def test_clinic_tenant_cannot_create_a_doctor(hospital_id):
    _set_hospital(hospital_id, password="clinic-pw", tenant_type="clinic", admin_capabilities=None)
    token = _login("clinic-pw")
    department = db.get_departments(hospital_id)[0]

    resp = client.post(
        "/api/portal/doctors",
        headers=_auth(token),
        json={
            "department_id": department["id"], "name": "Dr. Blocked", "specialization": "General",
            "qualification": "MBBS", "years_experience": "5", "working_days": ["Mon"],
            "working_hours": ["09:00-12:00"], "slot_duration_minutes": "30",
        },
    )
    assert resp.status_code == 403
    assert "manage_doctors" in resp.json()["error"]


def test_hospital_tenant_can_create_a_doctor(hospital_id):
    """Same request, a normal hospital-type tenant -- succeeds, proving the
    403 above is genuinely about the capability, not something else broken
    in the request shape."""
    _set_hospital(hospital_id, password="hospital-pw", tenant_type="hospital", admin_capabilities=None)
    token = _login("hospital-pw")
    department = db.get_departments(hospital_id)[0]

    resp = client.post(
        "/api/portal/doctors",
        headers=_auth(token),
        json={
            "department_id": department["id"], "name": "Dr. Allowed", "specialization": "General",
            "qualification": "MBBS", "years_experience": "5", "working_days": ["Mon"],
            "working_hours": ["09:00-12:00"], "slot_duration_minutes": "30",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["doctor"]["name"] == "Dr. Allowed"


def test_clinic_tenant_cannot_create_a_department(hospital_id):
    _set_hospital(hospital_id, password="clinic-pw2", tenant_type="clinic", admin_capabilities=None)
    token = _login("clinic-pw2")

    resp = client.post("/api/portal/departments", headers=_auth(token), json={"name": "New Dept"})
    assert resp.status_code == 403
    assert "manage_departments" in resp.json()["error"]


def test_clinic_tenant_can_still_view_doctors(hospital_id):
    """Read access is deliberately NOT gated -- a clinic still needs to see
    doctors/departments to book against them, it just can't manage them."""
    _set_hospital(hospital_id, password="clinic-pw3", tenant_type="clinic", admin_capabilities=None)
    token = _login("clinic-pw3")

    resp = client.get("/api/portal/doctors", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_explicit_admin_capabilities_override_lets_a_clinic_manage_doctors(hospital_id):
    """A clinic that's been explicitly granted manage_doctors (via the
    tenant-admin edit endpoint, tested separately below) is no longer
    blocked -- the gate reads the EFFECTIVE capability set, not just
    tenant_type."""
    _set_hospital(hospital_id, password="clinic-pw4", tenant_type="clinic", admin_capabilities=["manage_bookings", "manage_settings", "manage_doctors"])
    token = _login("clinic-pw4")
    department = db.get_departments(hospital_id)[0]

    resp = client.post(
        "/api/portal/doctors",
        headers=_auth(token),
        json={
            "department_id": department["id"], "name": "Dr. Granted", "specialization": "General",
            "qualification": "MBBS", "years_experience": "5", "working_days": ["Mon"],
            "working_hours": ["09:00-12:00"], "slot_duration_minutes": "30",
        },
    )
    assert resp.status_code == 200, resp.text


# --- admin/tenants_api.py: platform admin edits tenant_type/admin_capabilities ---

def test_tenant_admin_can_set_tenant_type_and_capabilities(hospital_id):
    before = db.get_hospital(hospital_id)
    assert before.tenant_type == "hospital"

    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_TENANTS_HEADERS, json={
        "name": before.name,
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
        "tenant_type": "clinic",
        "admin_capabilities": ["manage_bookings", "manage_settings"],
    })
    assert resp.status_code == 200, resp.text
    updated = db.get_hospital(hospital_id)
    assert updated.tenant_type == "clinic"
    assert set(updated.admin_capabilities) == {"manage_bookings", "manage_settings"}


def test_tenant_admin_rejects_unrecognized_tenant_type(hospital_id):
    before = db.get_hospital(hospital_id)
    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_TENANTS_HEADERS, json={
        "name": before.name,
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
        "tenant_type": "not_a_real_type",
    })
    assert resp.status_code == 400
    assert db.get_hospital(hospital_id).tenant_type == "hospital"


def test_tenant_admin_omitting_capability_fields_keeps_current_values(hospital_id):
    """Same "omitted means keep current" discipline enabled_features already
    follows on this endpoint -- a caller predating these two fields must not
    silently reset an already-configured clinic back to hospital/full-access."""
    before = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=before.name, whatsapp_phone_number_id=before.whatsapp_phone_number_id,
        access_token=before.access_token, app_secret=before.app_secret, timezone=before.timezone,
        welcome_message_text=before.welcome_message_text, reminder_offsets_hours=before.reminder_offsets_hours,
        reminder_template_name=before.reminder_template_name, data_tier=before.data_tier,
        external_api_base_url=before.external_api_base_url, external_api_key=before.external_api_key,
        portal_password_hash=before.portal_password_hash, enabled_features=before.enabled_features,
        tenant_type="clinic", admin_capabilities=["manage_bookings"],
    )

    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_TENANTS_HEADERS, json={
        "name": "Renamed Only",
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
    })
    assert resp.status_code == 200, resp.text
    updated = db.get_hospital(hospital_id)
    assert updated.name == "Renamed Only"
    assert updated.tenant_type == "clinic"
    assert updated.admin_capabilities == ["manage_bookings"]


def test_tenant_detail_reports_effective_capabilities(hospital_id):
    """_tenant_detail()'s admin_capabilities reflects the EFFECTIVE set
    (get_capabilities()) even when the column itself is unset -- an
    operator looking at a hospital-type tenant with no override sees the
    full default set, not an empty/null value."""
    resp = client.get(f"/api/admin/tenants/{hospital_id}", headers=_TENANTS_HEADERS)
    assert resp.status_code == 200, resp.text
    tenant = resp.json()["tenant"]
    assert tenant["tenant_type"] == "hospital"
    assert set(tenant["admin_capabilities"]) == DEFAULT_CAPABILITIES_BY_TYPE["hospital"]
    assert set(tenant["all_capabilities"]) == ALL_CAPABILITIES


# --- admin/onboarding_api.py: tenant_type at creation ---

def test_onboarding_sets_reduced_capabilities_for_a_clinic(hospital_id, user_auth_header):
    payload = {
        "admin_secret": "test-admin-secret",
        "name": "Downtown Walk-in Clinic",
        "whatsapp_phone_number_id": "CLINIC_PHONE_ID",
        "access_token": "clinic-token",
        "app_secret": "clinic-secret",
        "reminder_offsets_hours": "24",
        "portal_password": "clinic-bookings-pw",
        "enabled_features": ["booking"],
        "data_tier": "tier1",
        "departments": [{
            "name": "General",
            "doctors": [{
                "name": "Dr. Clinic Owner", "specialization": "General", "qualification": "MBBS",
                "years_experience": "5", "working_days": ["Mon"], "working_hours": ["09:00-12:00"],
                "slot_duration_minutes": "30",
            }],
        }],
        "topics": [],
        "tenant_type": "clinic",
    }
    resp = client.post("/api/onboarding", json=payload, headers=user_auth_header)
    assert resp.status_code == 200, resp.text

    hospital = db.find_hospital_by_phone_number_id("CLINIC_PHONE_ID")
    assert hospital is not None
    assert hospital.tenant_type == "clinic"
    assert set(hospital.admin_capabilities) == DEFAULT_CAPABILITIES_BY_TYPE["clinic"]


def test_onboarding_defaults_to_hospital_type_when_omitted(hospital_id, user_auth_header):
    """Backward compatibility: any caller that predates tenant_type (the
    existing Next.js wizard, until it's updated) keeps getting full
    hospital-type admin capabilities, unchanged."""
    payload = {
        "admin_secret": "test-admin-secret",
        "name": "Legacy Wizard Hospital",
        "whatsapp_phone_number_id": "LEGACY_PHONE_ID",
        "reminder_offsets_hours": "24",
        "portal_password": "legacy-pw",
        "enabled_features": ["booking"],
        "data_tier": "tier1",
        "departments": [{
            "name": "General",
            "doctors": [{
                "name": "Dr. Legacy", "specialization": "General", "qualification": "MBBS",
                "years_experience": "5", "working_days": ["Mon"], "working_hours": ["09:00-12:00"],
                "slot_duration_minutes": "30",
            }],
        }],
        "topics": [],
    }
    resp = client.post("/api/onboarding", json=payload, headers=user_auth_header)
    assert resp.status_code == 200, resp.text

    hospital = db.find_hospital_by_phone_number_id("LEGACY_PHONE_ID")
    assert hospital.tenant_type == "hospital"
    assert set(hospital.admin_capabilities) == DEFAULT_CAPABILITIES_BY_TYPE["hospital"]


# --- Follow-up: tenant-aware appointment type defaults (the "daycare" gap) ---

def test_daycare_is_active_by_default_for_hospital_but_not_clinic(hospital_id, user_auth_header):
    """DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE (db/repositories/appointment_types.py):
    every tenant gets a row for every type at creation, but 'daycare' starts
    inactive for a clinic -- proving the hospital-only-feature gap flagged in
    tenant-capability-gating-plan.md's follow-up is actually closed, not just
    documented."""
    payload = {
        "admin_secret": "test-admin-secret",
        "name": "Daycare Gap Clinic",
        "whatsapp_phone_number_id": "DAYCARE_CLINIC_PHONE_ID",
        "reminder_offsets_hours": "24",
        "portal_password": "daycare-clinic-pw",
        "enabled_features": ["booking"],
        "data_tier": "tier1",
        "departments": [{
            "name": "General",
            "doctors": [{
                "name": "Dr. Clinic", "specialization": "General", "qualification": "MBBS",
                "years_experience": "5", "working_days": ["Mon"], "working_hours": ["09:00-12:00"],
                "slot_duration_minutes": "30",
            }],
        }],
        "topics": [],
        "tenant_type": "clinic",
    }
    resp = client.post("/api/onboarding", json=payload, headers=user_auth_header)
    assert resp.status_code == 200, resp.text
    clinic = db.find_hospital_by_phone_number_id("DAYCARE_CLINIC_PHONE_ID")

    clinic_types = {t["id"]: t["is_active"] for t in db.get_all_appointment_types_for_hospital(clinic.id)}
    hospital_types = {t["id"]: t["is_active"] for t in db.get_all_appointment_types_for_hospital(hospital_id)}

    assert "daycare" in clinic_types and clinic_types["daycare"] is False
    assert "daycare" in hospital_types and hospital_types["daycare"] is True
    # Every other default type stays active for both -- only daycare differs.
    assert {k: v for k, v in clinic_types.items() if k != "daycare"} == \
        {k: True for k in clinic_types if k != "daycare"}


# --- Portal appointment-type CRUD (manage_appointment_types capability) ---

def test_clinic_cannot_toggle_appointment_types_without_the_capability(hospital_id):
    _set_hospital(hospital_id, password="apttype-pw", tenant_type="clinic", admin_capabilities=None)
    token = _login("apttype-pw")

    resp = client.post(
        "/api/portal/appointment-types/daycare/active", headers=_auth(token), json={"is_active": True},
    )
    assert resp.status_code == 403
    assert "manage_appointment_types" in resp.json()["error"]


def test_clinic_can_turn_on_daycare_once_granted_the_capability(user_auth_header):
    """The exact "clinic wants a hospital-only feature turned on" scenario
    tenant-capability-gating-plan.md's follow-up describes: no re-onboarding,
    no data loss, just a capability grant + an is_active flip. Onboards a
    genuine clinic (rather than flipping an existing hospital's tenant_type
    in place) since is_active is resolved once, at seed time -- retagging an
    already-seeded hospital's tenant_type does NOT retroactively touch rows
    seeded under its old type, by design (see this file's downgrade test)."""
    payload = {
        "admin_secret": "test-admin-secret",
        "name": "Growing Clinic",
        "whatsapp_phone_number_id": "GROWING_CLINIC_PHONE_ID",
        "reminder_offsets_hours": "24",
        "portal_password": "apttype-pw2",
        "enabled_features": ["booking"],
        "data_tier": "tier1",
        "departments": [{
            "name": "General",
            "doctors": [{
                "name": "Dr. Growing", "specialization": "General", "qualification": "MBBS",
                "years_experience": "5", "working_days": ["Mon"], "working_hours": ["09:00-12:00"],
                "slot_duration_minutes": "30",
            }],
        }],
        "topics": [],
        "tenant_type": "clinic",
    }
    resp = client.post("/api/onboarding", json=payload, headers=user_auth_header)
    assert resp.status_code == 200, resp.text
    clinic_id = resp.json()["hospital_id"]

    resp = client.post(f"/api/admin/tenants/{clinic_id}", headers=_TENANTS_HEADERS, json={
        "name": "Growing Clinic",
        "whatsapp_phone_number_id": "GROWING_CLINIC_PHONE_ID",
        "data_tier": "tier1",
        "admin_capabilities": ["manage_bookings", "manage_settings", "manage_appointment_types"],
    })
    assert resp.status_code == 200, resp.text

    token = _login("apttype-pw2")
    before = {t["id"]: t["is_active"] for t in db.get_all_appointment_types_for_hospital(clinic_id)}
    assert before["daycare"] is False

    resp = client.post(
        "/api/portal/appointment-types/daycare/active", headers=_auth(token), json={"is_active": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["appointment_type"]["is_active"] is True

    after = {t["id"]: t["is_active"] for t in db.get_all_appointment_types_for_hospital(clinic_id)}
    assert after["daycare"] is True
    # Nothing else about the tenant's data changed by this toggle.
    assert {k: v for k, v in after.items() if k != "daycare"} == {k: v for k, v in before.items() if k != "daycare"}
    assert any(t["id"] == "daycare" for t in db.get_appointment_types(clinic_id))


def test_appointment_type_toggle_rejects_unknown_id(hospital_id):
    _set_hospital(hospital_id, password="apttype-pw3", tenant_type="hospital", admin_capabilities=None)
    token = _login("apttype-pw3")
    resp = client.post(
        "/api/portal/appointment-types/not_a_real_type/active", headers=_auth(token), json={"is_active": True},
    )
    assert resp.status_code == 404


# --- Downgrade/upgrade safety: capability changes never touch underlying data ---

def test_downgrading_a_hospital_to_clinic_never_deletes_departments_or_doctors(hospital_id):
    """The whole point of the toggle: capability gating hides portal
    management routes, it never deletes or hides the underlying data --
    departments/doctors/appointment types the tenant already had stay fully
    intact and bookable after a downgrade."""
    departments_before = db.get_departments(hospital_id)
    doctors_before = db.get_all_doctors_for_hospital(hospital_id)
    assert departments_before and doctors_before

    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_TENANTS_HEADERS, json={
        "name": db.get_hospital(hospital_id).name,
        "whatsapp_phone_number_id": db.get_hospital(hospital_id).whatsapp_phone_number_id,
        "data_tier": "tier1",
        "tenant_type": "clinic",
        "admin_capabilities": sorted(DEFAULT_CAPABILITIES_BY_TYPE["clinic"]),
    })
    assert resp.status_code == 200, resp.text

    departments_after = db.get_departments(hospital_id)
    doctors_after = db.get_all_doctors_for_hospital(hospital_id)
    assert departments_after == departments_before
    assert doctors_after == doctors_before

    # Still readable/bookable via the portal (never capability-gated), just
    # not manageable any more.
    _set_hospital(hospital_id, password="downgrade-pw", tenant_type="clinic", admin_capabilities=sorted(DEFAULT_CAPABILITIES_BY_TYPE["clinic"]))
    token = _login("downgrade-pw")
    resp = client.get("/api/portal/doctors", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["doctors"]

    resp = client.post("/api/portal/departments", headers=_auth(token), json={"name": "New Dept"})
    assert resp.status_code == 403


# --- Audit trail: platform_admin and portal levels, secret redaction ---

def test_tenant_update_records_a_platform_admin_audit_entry(hospital_id):
    before = db.get_hospital(hospital_id)
    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_TENANTS_HEADERS, json={
        "name": before.name,
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
        "tenant_type": "clinic",
        "admin_capabilities": ["manage_bookings"],
    })
    assert resp.status_code == 200, resp.text

    entries = db.get_audit_logs(hospital_id=hospital_id, actor_level="platform_admin")
    tenant_type_entries = [e for e in entries if e["action"] == "tenant.update"]
    assert tenant_type_entries
    entry = tenant_type_entries[0]
    assert entry["before_value"]["tenant_type"] == "hospital"
    assert entry["after_value"]["tenant_type"] == "clinic"


def test_doctor_create_records_a_portal_level_audit_entry(hospital_id):
    _set_hospital(hospital_id, password="audit-pw", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-pw")
    department = db.get_departments(hospital_id)[0]

    resp = client.post(
        "/api/portal/doctors",
        headers=_auth(token),
        json={
            "department_id": department["id"], "name": "Dr. Audited", "specialization": "General",
            "qualification": "MBBS", "years_experience": "5", "working_days": ["Mon"],
            "working_hours": ["09:00-12:00"], "slot_duration_minutes": "30",
        },
    )
    assert resp.status_code == 200, resp.text

    portal_entries = db.get_audit_logs(hospital_id=hospital_id, actor_level="portal")
    assert any(e["action"] == "doctor.create" and e["after_value"]["name"] == "Dr. Audited" for e in portal_entries)
    # Portal-level query never returns platform_admin rows even if some exist.
    assert all(e["actor_level"] == "portal" for e in portal_entries)


def test_audit_log_redacts_secret_fields(hospital_id):
    from db.repositories.audit_logs import record_audit_log

    record_audit_log(
        "platform_admin", hospital_id, "platform admin", "tenant.update",
        before={"access_token": "old-real-token", "name": "Old Name"},
        after={"access_token": "new-real-token", "name": "New Name"},
    )
    entries = db.get_audit_logs(hospital_id=hospital_id, actor_level="platform_admin")
    entry = next(e for e in entries if e["action"] == "tenant.update" and e["after_value"]["name"] == "New Name")
    assert entry["before_value"]["access_token"] == "<changed>"
    assert entry["after_value"]["access_token"] == "<changed>"
    assert "old-real-token" not in str(entry) and "new-real-token" not in str(entry)


def test_portal_audit_log_route_requires_manage_settings(hospital_id):
    _set_hospital(hospital_id, password="audit-route-pw", tenant_type="clinic", admin_capabilities=["manage_bookings"])
    token = _login("audit-route-pw")
    resp = client.get("/api/portal/audit-log", headers=_auth(token))
    assert resp.status_code == 403


def test_platform_audit_log_route_lists_across_tenants_with_hospital_name(hospital_id, second_hospital_id):
    """GET /api/admin/audit-log (unlike the per-tenant route) is the
    cross-tenant view -- a platform admin browsing recent activity without
    opening every tenant's edit page individually."""
    before = db.get_hospital(hospital_id)
    client.post(f"/api/admin/tenants/{hospital_id}", headers=_TENANTS_HEADERS, json={
        "name": before.name,
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
        "tenant_type": "clinic",
        "admin_capabilities": ["manage_bookings"],
    })

    resp = client.get("/api/admin/audit-log", headers=_TENANTS_HEADERS)
    assert resp.status_code == 200, resp.text
    entries = resp.json()["entries"]
    assert any(e["hospital_id"] == hospital_id and e["hospital_name"] == before.name for e in entries)

    # hospital_id filter narrows it down to one tenant, same rows the
    # per-tenant route would show.
    resp = client.get("/api/admin/audit-log", headers=_TENANTS_HEADERS, params={"hospital_id": hospital_id})
    assert resp.status_code == 200, resp.text
    scoped = resp.json()["entries"]
    assert scoped and all(e["hospital_id"] == hospital_id for e in scoped)

    resp = client.get("/api/admin/audit-log", headers=_TENANTS_HEADERS, params={"actor_level": "not_a_real_level"})
    assert resp.status_code == 400


def test_portal_audit_log_route_returns_only_this_tenants_portal_rows(hospital_id, second_hospital_id):
    _set_hospital(hospital_id, password="audit-route-pw2", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-route-pw2")
    department = db.get_departments(hospital_id)[0]
    client.post(
        "/api/portal/doctors", headers=_auth(token),
        json={
            "department_id": department["id"], "name": "Dr. Own Tenant", "specialization": "General",
            "qualification": "MBBS", "years_experience": "5", "working_days": ["Mon"],
            "working_hours": ["09:00-12:00"], "slot_duration_minutes": "30",
        },
    )
    resp = client.get("/api/portal/audit-log", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    entries = resp.json()["entries"]
    assert all(e["hospital_id"] == hospital_id for e in entries)
    assert not any(e["hospital_id"] == second_hospital_id for e in entries)


# --- Audit coverage follow-up: patients.py, bookings.py, handoffs.py ---
# (skips reply/note/document CONTENT and high-VOLUME scheduling actions
# (leave/slots/csv-import) per explicit scope agreement -- only patient-
# and booking-affecting actions are audited here.)

def _own_portal_actions(hospital_id):
    return [e["action"] for e in db.get_audit_logs(hospital_id=hospital_id, actor_level="portal")]


def _book_appointment(hospital_id, phone="5490009999"):
    department = db.get_departments(hospital_id)[0]
    doctor = db.get_all_doctors_for_hospital(hospital_id)[0]
    slot = db.get_slots(hospital_id, doctor["id"])[0]
    return db.create_appointment(
        hospital_id, phone, department["id"], doctor["id"], datetime.fromisoformat(slot["id"]),
    ), department, doctor


def test_patient_delete_records_an_audit_entry(hospital_id):
    _set_hospital(hospital_id, password="audit-patient-pw", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-patient-pw")
    appointment, _, _ = _book_appointment(hospital_id)
    patient_id = appointment.patient_id

    resp = client.post(
        "/api/portal/patients/delete", headers=_auth(token), json={"patient_ids": [patient_id]},
    )
    assert resp.status_code == 200, resp.text
    assert "patient.delete" in _own_portal_actions(hospital_id)


def test_patient_update_and_status_change_record_audit_entries(hospital_id):
    _set_hospital(hospital_id, password="audit-patient-pw2", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-patient-pw2")
    appointment, _, _ = _book_appointment(hospital_id, phone="5490009998")
    patient_id = appointment.patient_id

    resp = client.post(
        f"/api/portal/patients/{patient_id}", headers=_auth(token), json={"gender": "Female"},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        f"/api/portal/patients/{patient_id}/status", headers=_auth(token), json={"status": "blocked"},
    )
    assert resp.status_code == 200, resp.text

    actions = _own_portal_actions(hospital_id)
    assert "patient.update" in actions
    assert "patient.status_change" in actions


def test_booking_lifecycle_records_audit_entries(hospital_id):
    _set_hospital(hospital_id, password="audit-booking-pw", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-booking-pw")
    department = db.get_departments(hospital_id)[0]
    doctor = db.get_all_doctors_for_hospital(hospital_id)[0]
    slots = db.get_slots(hospital_id, doctor["id"])

    resp = client.post(
        "/api/portal/new-booking", headers=_auth(token),
        json={
            "patient_name": "Audit Patient", "patient_phone": "5490007777",
            "department_id": department["id"], "doctor_id": doctor["id"], "slot_id": slots[0]["id"],
        },
    )
    assert resp.status_code == 200, resp.text

    appointment = db.get_active_appointments_for_patient(
        hospital_id, db.get_patient_by_phone(hospital_id, "5490007777")["id"],
    )[0]

    resp = client.post(
        f"/api/portal/bookings/{appointment.id}/attendance", headers=_auth(token), json={"attended": True},
    )
    assert resp.status_code == 200, resp.text

    actions = _own_portal_actions(hospital_id)
    assert "booking.create" in actions
    assert "booking.attendance" in actions


def test_booking_cancel_and_reschedule_record_audit_entries(hospital_id):
    _set_hospital(hospital_id, password="audit-booking-pw2", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-booking-pw2")
    appointment, department, doctor = _book_appointment(hospital_id, phone="5490006666")
    slots = db.get_slots(hospital_id, doctor["id"])
    other_slot = next(s for s in slots if s["id"] != appointment.scheduled_at.isoformat())

    resp = client.post(
        f"/api/portal/bookings/{appointment.id}/reschedule", headers=_auth(token),
        json={"department_id": department["id"], "doctor_id": doctor["id"], "slot_id": other_slot["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert "booking.reschedule" in _own_portal_actions(hospital_id)

    resp = client.post(f"/api/portal/bookings/{appointment.id}/cancel", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert "booking.cancel" in _own_portal_actions(hospital_id)


def test_booking_delete_records_an_audit_entry(hospital_id):
    _set_hospital(hospital_id, password="audit-booking-pw3", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-booking-pw3")
    appointment, _, _ = _book_appointment(hospital_id, phone="5490005555")
    client.post(f"/api/portal/bookings/{appointment.id}/cancel", headers=_auth(token))

    resp = client.post(f"/api/portal/bookings/{appointment.id}/delete", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert "booking.delete" in _own_portal_actions(hospital_id)


def test_handoff_resolve_and_delete_record_audit_entries(hospital_id):
    _set_hospital(hospital_id, password="audit-handoff-pw", tenant_type="hospital", admin_capabilities=None)
    token = _login("audit-handoff-pw")
    handoff = db.create_handoff_request(hospital_id, "5490004444", "patient_requested")

    resp = client.post(f"/api/portal/handoffs/{handoff['id']}/resolve", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert "handoffs.resolve" in _own_portal_actions(hospital_id)

    handoff2 = db.create_handoff_request(hospital_id, "5490003333", "patient_requested")
    resp = client.post(f"/api/portal/handoffs/{handoff2['id']}/delete", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert "handoffs.delete" in _own_portal_actions(hospital_id)
