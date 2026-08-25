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
from app import app  # noqa: E402
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


def test_update_can_enable_a_new_feature_for_an_existing_tenant(hospital_id):
    """Feature-toggle follow-up (Spec.md Section 0): enabled_features was
    previously only ever set once, at onboarding, with no way anywhere in
    this app to turn a feature on for an already-onboarded tenant -- this
    is the fix, an operator can now toggle any REAL_FEATURES key here."""
    before = db.get_hospital(hospital_id)
    assert "manage_patients" not in before.enabled_features

    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_HEADERS, json={
        "name": before.name,
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
        "enabled_features": [*before.enabled_features, "manage_patients"],
    })
    assert resp.status_code == 200, resp.text
    updated = db.get_hospital(hospital_id)
    assert "manage_patients" in updated.enabled_features
    for key in before.enabled_features:
        assert key in updated.enabled_features


def test_update_omitting_enabled_features_keeps_the_current_value(hospital_id):
    """Same "blank/omitted means keep current" rule every other field on
    this endpoint already follows (blank token/secret/password) -- a
    request that doesn't mention enabled_features at all (any caller
    predating this field) must not silently wipe it to empty."""
    before = db.get_hospital(hospital_id)
    assert before.enabled_features  # the seeded hospital has some enabled

    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_HEADERS, json={
        "name": before.name,
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
    })
    assert resp.status_code == 200, resp.text
    updated = db.get_hospital(hospital_id)
    assert sorted(updated.enabled_features) == sorted(before.enabled_features)


def test_update_with_explicit_empty_enabled_features_disables_everything(hospital_id):
    """The other half of the same distinction: an explicit [] (every
    checkbox unticked in the UI) IS a deliberate "disable everything" and
    must be honored, not treated the same as "field not sent.\""""
    before = db.get_hospital(hospital_id)
    assert before.enabled_features

    resp = client.post(f"/api/admin/tenants/{hospital_id}", headers=_HEADERS, json={
        "name": before.name,
        "whatsapp_phone_number_id": before.whatsapp_phone_number_id,
        "data_tier": "tier1",
        "enabled_features": [],
    })
    assert resp.status_code == 200, resp.text
    updated = db.get_hospital(hospital_id)
    assert updated.enabled_features == []


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


# --- Item 5: stalled Google signups (Spec.md Section 0) ---


def test_stalled_signups_lists_users_with_no_hospital(hospital_id):
    stalled = db.create_user(email="stalled@example.com", google_id="g-stalled", name="Stalled Person")
    owner = db.create_user(email="owner@example.com", google_id="g-owner", name="Real Owner")
    db.link_hospital_owner(hospital_id, owner.id)

    resp = client.get("/api/admin/stalled-signups", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    emails = {u["email"] for u in resp.json()["users"]}
    assert emails == {"stalled@example.com"}
    assert emails.isdisjoint({"owner@example.com"})

    row = next(u for u in resp.json()["users"] if u["id"] == stalled.id)
    assert row["name"] == "Stalled Person"


def test_stalled_signups_requires_secret(hospital_id):
    db.create_user(email="stalled@example.com", google_id="g-stalled")
    resp = client.get("/api/admin/stalled-signups")
    assert resp.status_code == 401


def test_total_bookings_stat_counts_every_booking_across_hospitals(hospital_id, second_hospital_id):
    from datetime import datetime

    before = client.get("/api/admin/stats/total-bookings", headers=_HEADERS).json()["total_bookings"]

    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    slot = db.get_slots(hospital_id, doctor_id)[0]
    appt = db.create_appointment(
        hospital_id, "5490001111", "cardiology", doctor_id, datetime.fromisoformat(slot["id"]),
        patient_name="Ravi Kumar", patient_age=34,
    )
    t2_doctor_id = db.get_doctors(second_hospital_id, "t2_neurology")[0]["id"]
    t2_slot = db.get_slots(second_hospital_id, t2_doctor_id)[0]
    db.create_appointment(
        second_hospital_id, "5490002222", "t2_neurology", t2_doctor_id, datetime.fromisoformat(t2_slot["id"]),
        patient_name="Cross Tenant", patient_age=40,
    )

    # Cancelling doesn't reduce the lifetime count -- item 7's own definition.
    db.cancel_appointment(hospital_id, appt.id)

    resp = client.get("/api/admin/stats/total-bookings", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total_bookings"] == before + 2


def test_total_bookings_stat_requires_secret(hospital_id):
    resp = client.get("/api/admin/stats/total-bookings")
    assert resp.status_code == 401
