# tests/test_tenants_api.py
"""
JSON API equivalent of the old tests/test_admin_tenant_edit.py (deleted) --
that tested admin/onboarding.py's server-rendered HTML tenant list/edit
pages, which were removed once the Next.js frontend
(frontend/src/app/admin/tenants, admin/edit-tenant/[id]) became the real
platform-admin UI. Ported rather than dropped: admin/tenants_api.py's
update_tenant()/list_tenants() are the currently-live code these pages
actually call.

Gated by TENANTS_ADMIN_SECRET via an X-Admin-Secret header (not
ADMIN_SECRET, not a Bearer token) -- deliberately a different secret from
onboarding's, per this module's own docstring.
"""
import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")

import db.repository as db  # noqa: E402
from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

TENANTS_ADMIN_SECRET = "test-tenants-admin-secret"
_HEADERS = {"X-Admin-Secret": TENANTS_ADMIN_SECRET}


def test_list_tenants_requires_secret(hospital_id, second_hospital_id):
    resp = client.get("/api/admin/tenants")
    assert resp.status_code == 401

    resp = client.get("/api/admin/tenants", headers={"X-Admin-Secret": "wrong"})
    assert resp.status_code == 401


def test_list_tenants_shows_all_tenants(hospital_id, second_hospital_id):
    resp = client.get("/api/admin/tenants", headers=_HEADERS)
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()["tenants"]}
    assert {hospital_id, second_hospital_id} <= ids


def test_get_tenant_prefilled_with_masked_secrets(hospital_id):
    resp = client.get(f"/api/admin/tenants/{hospital_id}", headers=_HEADERS)
    assert resp.status_code == 200
    tenant = resp.json()["tenant"]
    assert tenant["id"] == hospital_id
    # Masked, not the raw secret.
    assert "••••" in tenant["access_token_masked"]


def test_get_nonexistent_tenant_returns_404(hospital_id):
    resp = client.get("/api/admin/tenants/999999", headers=_HEADERS)
    assert resp.status_code == 404


def test_update_changes_the_correct_fields_and_keeps_blank_secret_unchanged(hospital_id):
    original_app_secret = db.get_hospital(hospital_id).app_secret
    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_HEADERS, json={
        "name": "Renamed Hospital",
        "whatsapp_phone_number_id": "123",
        "access_token": "brand-new-token",
        "app_secret": "",  # left blank -> must keep the old value, not erase it
        "welcome_message_text": "New welcome text",
        "reminder_offsets_hours": "48,2",
        "reminder_template_name": "new_template",
        "data_tier": "tier1",
        "api_base_url": "",
        "api_key": "",
    })
    assert resp.status_code == 200, resp.text
    updated = db.get_hospital(hospital_id)
    assert updated.name == "Renamed Hospital"
    assert updated.access_token == "brand-new-token"
    assert updated.app_secret == original_app_secret
    assert sorted(updated.reminder_offsets_hours) == [2, 48]


def test_update_uniqueness_constraint_enforced_on_phone_number_id_change(hospital_id, second_hospital_id):
    hosp1_before = db.get_hospital(hospital_id)
    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_HEADERS, json={
        "name": hosp1_before.name,
        "whatsapp_phone_number_id": "TEST_HOSPITAL_2_PHONE_ID",  # already used by the other tenant
        "data_tier": "tier1",
    })
    assert resp.status_code == 400
    assert "already exists" in resp.json()["errors"][0]
    hosp1_after = db.get_hospital(hospital_id)
    assert hosp1_after.whatsapp_phone_number_id == hosp1_before.whatsapp_phone_number_id


def test_update_unchanged_phone_number_id_does_not_conflict_with_itself(hospital_id):
    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_HEADERS, json={
        "name": "Still Works Hospital",
        "whatsapp_phone_number_id": "123",  # its own existing value, unchanged
        "data_tier": "tier1",
    })
    assert resp.status_code == 200, resp.text
    assert db.get_hospital(hospital_id).name == "Still Works Hospital"


def test_update_wrong_secret_rejected(hospital_id):
    hosp_before = db.get_hospital(hospital_id)
    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers={"X-Admin-Secret": "wrong"}, json={
        "name": "Should Not Apply", "whatsapp_phone_number_id": "123", "data_tier": "tier1",
    })
    assert resp.status_code == 401
    assert db.get_hospital(hospital_id).name == hosp_before.name


def test_update_nonexistent_tenant_returns_404(hospital_id):
    resp = client.post("/api/admin/tenants/999999", headers=_HEADERS, json={
        "name": "Ghost", "whatsapp_phone_number_id": "ghost-id", "data_tier": "tier1",
    })
    assert resp.status_code == 404


def test_assign_owner_by_email_creates_placeholder_user_and_links(hospital_id):
    resp = client.post(f"/api/admin/tenants/{hospital_id}/assign-owner", headers=_HEADERS, json={
        "email": "owner@example.com",
    })
    assert resp.status_code == 200, resp.text
    owners = db.get_owners_for_hospital(hospital_id)
    assert len(owners) == 1
    assert owners[0].email == "owner@example.com"
    assert owners[0].google_id is None  # placeholder -- backfilled on first real Google sign-in

    # Idempotent: assigning the same email again doesn't create a duplicate.
    resp2 = client.post(f"/api/admin/tenants/{hospital_id}/assign-owner", headers=_HEADERS, json={
        "email": "owner@example.com",
    })
    assert resp2.status_code == 200
    assert len(db.get_owners_for_hospital(hospital_id)) == 1


def test_assign_owner_requires_secret(hospital_id):
    resp = client.post(f"/api/admin/tenants/{hospital_id}/assign-owner", json={"email": "owner@example.com"})
    assert resp.status_code == 401
    assert db.get_owners_for_hospital(hospital_id) == []
