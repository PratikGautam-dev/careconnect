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

import db.repository as db  # noqa: E402
from backend.main import app  # noqa: E402
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
