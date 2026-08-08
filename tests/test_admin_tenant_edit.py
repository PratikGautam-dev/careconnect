# tests/test_admin_tenant_edit.py
"""
SPEC Section 12.1 follow-up: onboarding (POST /admin/onboard-hospital) is
create-only -- there was no way to correct an already-onboarded tenant's
credentials except a direct SQL UPDATE. This closes that gap:
GET /admin/tenants (list, links to edit each) and GET/POST
/admin/edit-tenant/{id} (pre-filled edit form -> db.update_hospital()),
both gated by the same ADMIN_SECRET check the onboarding wizard uses.
"""
import os

import db.repository as db

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")

from core.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

ADMIN_SECRET = "test-admin-secret"


def test_tenants_list_requires_admin_secret(hospital_id, second_hospital_id):
    resp = client.get("/admin/tenants")
    assert resp.status_code == 200  # no secret at all -> shows the gate form, not tenant data
    assert "St." not in resp.text and "TEST_HOSPITAL_2_PHONE_ID" not in resp.text

    resp = client.get("/admin/tenants", params={"secret": "wrong"})
    assert resp.status_code == 403
    assert "TEST_HOSPITAL_2_PHONE_ID" not in resp.text


def test_tenants_list_shows_all_tenants(hospital_id, second_hospital_id):
    resp = client.get("/admin/tenants", params={"secret": ADMIN_SECRET})
    assert resp.status_code == 200
    hosp1 = db.get_hospital(hospital_id)
    hosp2 = db.get_hospital(second_hospital_id)
    assert hosp1.name in resp.text
    assert hosp2.name in resp.text
    assert "123" in resp.text
    assert "TEST_HOSPITAL_2_PHONE_ID" in resp.text
    assert f"/admin/edit-tenant/{hospital_id}" in resp.text
    assert f"/admin/edit-tenant/{second_hospital_id}" in resp.text


def test_edit_tenant_form_requires_admin_secret(hospital_id):
    resp = client.get(f"/admin/edit-tenant/{hospital_id}")
    assert resp.status_code == 200  # gate form, no tenant data leaked
    assert 'name="whatsapp_phone_number_id"' not in resp.text

    resp = client.get(f"/admin/edit-tenant/{hospital_id}", params={"secret": "wrong"})
    assert resp.status_code == 403
    assert 'name="whatsapp_phone_number_id"' not in resp.text


def test_edit_tenant_form_prefilled_with_masked_secrets(hospital_id):
    hospital = db.get_hospital(hospital_id)
    resp = client.get(f"/admin/edit-tenant/{hospital_id}", params={"secret": ADMIN_SECRET})
    assert resp.status_code == 200
    assert hospital.name in resp.text
    assert hospital.whatsapp_phone_number_id in resp.text
    # The token/secret inputs themselves must start blank (never pre-filled
    # with the real value) -- only their placeholder hint shows a masked form.
    assert 'id="access_token" name="access_token" placeholder="Leave blank to keep current' in resp.text
    assert 'id="app_secret" name="app_secret" placeholder="Leave blank to keep current' in resp.text
    assert "••••" in resp.text  # masked hint, not the raw secret


def test_edit_updates_the_correct_fields(hospital_id):
    original_app_secret = db.get_hospital(hospital_id).app_secret
    resp = client.post(f"/admin/edit-tenant/{hospital_id}", data={
        "admin_secret": ADMIN_SECRET,
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
    assert resp.status_code == 200
    assert "Tenant updated" in resp.text
    assert "changes take effect after the app restarts, not immediately" in resp.text

    updated = db.get_hospital(hospital_id)
    assert updated.name == "Renamed Hospital"
    assert updated.access_token == "brand-new-token"
    assert updated.app_secret == original_app_secret  # unchanged, blank field kept it
    assert updated.welcome_message_text == "New welcome text"
    assert sorted(updated.reminder_offsets_hours) == [2, 48]
    assert updated.reminder_template_name == "new_template"


def test_edit_uniqueness_constraint_enforced_on_phone_number_id_change(hospital_id, second_hospital_id):
    hosp1_before = db.get_hospital(hospital_id)
    resp = client.post(f"/admin/edit-tenant/{hospital_id}", data={
        "admin_secret": ADMIN_SECRET,
        "name": hosp1_before.name,
        "whatsapp_phone_number_id": "TEST_HOSPITAL_2_PHONE_ID",  # already used by the other tenant
        "access_token": "",
        "app_secret": "",
        "welcome_message_text": "",
        "reminder_offsets_hours": "24",
        "reminder_template_name": "",
        "data_tier": "tier1",
        "api_base_url": "",
        "api_key": "",
    })
    assert resp.status_code == 400
    assert "already exists" in resp.text

    hosp1_after = db.get_hospital(hospital_id)
    assert hosp1_after.whatsapp_phone_number_id == hosp1_before.whatsapp_phone_number_id  # untouched


def test_edit_unchanged_phone_number_id_does_not_conflict_with_itself(hospital_id):
    resp = client.post(f"/admin/edit-tenant/{hospital_id}", data={
        "admin_secret": ADMIN_SECRET,
        "name": "Still Works Hospital",
        "whatsapp_phone_number_id": "123",  # its own existing value, unchanged
        "access_token": "",
        "app_secret": "",
        "welcome_message_text": "",
        "reminder_offsets_hours": "24",
        "reminder_template_name": "",
        "data_tier": "tier1",
        "api_base_url": "",
        "api_key": "",
    })
    assert resp.status_code == 200
    assert "Tenant updated" in resp.text
    assert db.get_hospital(hospital_id).name == "Still Works Hospital"


def test_edit_wrong_admin_secret_rejected(hospital_id):
    hosp_before = db.get_hospital(hospital_id)
    resp = client.post(f"/admin/edit-tenant/{hospital_id}", data={
        "admin_secret": "wrong-secret",
        "name": "Should Not Apply",
        "whatsapp_phone_number_id": "123",
        "access_token": "",
        "app_secret": "",
        "welcome_message_text": "",
        "reminder_offsets_hours": "24",
        "reminder_template_name": "",
        "data_tier": "tier1",
        "api_base_url": "",
        "api_key": "",
    })
    assert resp.status_code == 403
    assert db.get_hospital(hospital_id).name == hosp_before.name


def test_edit_missing_admin_secret_rejected(hospital_id):
    hosp_before = db.get_hospital(hospital_id)
    resp = client.post(f"/admin/edit-tenant/{hospital_id}", data={
        "name": "Should Not Apply",
        "whatsapp_phone_number_id": "123",
        "reminder_offsets_hours": "24",
        "data_tier": "tier1",
    })
    assert resp.status_code == 403
    assert db.get_hospital(hospital_id).name == hosp_before.name


def test_edit_nonexistent_tenant_returns_404(hospital_id):
    resp = client.get("/admin/edit-tenant/999999", params={"secret": ADMIN_SECRET})
    assert resp.status_code == 404

    resp = client.post("/admin/edit-tenant/999999", data={
        "admin_secret": ADMIN_SECRET,
        "name": "Ghost",
        "whatsapp_phone_number_id": "ghost-id",
        "reminder_offsets_hours": "24",
        "data_tier": "tier1",
    })
    assert resp.status_code == 404
