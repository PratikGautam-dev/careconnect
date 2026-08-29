# tests/test_platform_settings_api.py
"""
admin/platform_settings_api.py -- the platform/super admin's GLOBAL settings
endpoint (as opposed to tests/test_tenants_api.py, which is about one
tenant's own row). Same TENANTS_ADMIN_SECRET gate, same X-Admin-Secret
header convention, per that module's own docstring.
"""
import os

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")

from main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

TENANTS_ADMIN_SECRET = "test-tenants-admin-secret"
_HEADERS = {"X-Admin-Secret": TENANTS_ADMIN_SECRET}


def test_get_platform_settings_requires_secret():
    resp = client.get("/api/admin/platform-settings")
    assert resp.status_code == 401

    resp = client.get("/api/admin/platform-settings", headers={"X-Admin-Secret": "wrong"})
    assert resp.status_code == 401


def test_get_platform_settings_returns_the_current_value():
    resp = client.get("/api/admin/platform-settings", headers=_HEADERS)
    assert resp.status_code == 200
    assert "max_active_patient_links" in resp.json()


def test_update_platform_settings_changes_the_value_globally():
    original = client.get("/api/admin/platform-settings", headers=_HEADERS).json()["max_active_patient_links"]
    try:
        resp = client.post("/api/admin/platform-settings", json={"max_active_patient_links": 3}, headers=_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["max_active_patient_links"] == 3

        # A fresh read reflects the change -- not just the response body.
        resp = client.get("/api/admin/platform-settings", headers=_HEADERS)
        assert resp.json()["max_active_patient_links"] == 3
    finally:
        client.post("/api/admin/platform-settings", json={"max_active_patient_links": original}, headers=_HEADERS)


def test_update_platform_settings_requires_secret():
    resp = client.post("/api/admin/platform-settings", json={"max_active_patient_links": 3})
    assert resp.status_code == 401


def test_update_platform_settings_rejects_out_of_range_values():
    resp = client.post("/api/admin/platform-settings", json={"max_active_patient_links": 0}, headers=_HEADERS)
    assert resp.status_code == 400

    resp = client.post("/api/admin/platform-settings", json={"max_active_patient_links": 21}, headers=_HEADERS)
    assert resp.status_code == 400


def test_get_max_active_patient_links_falls_back_to_default_on_read_failure(hospital_id):
    """The booking/manage-patients flow must not crash if the platform_
    settings read itself fails (a transient DB hiccup) -- db/repositories/
    platform_settings.py's get_max_active_patient_links() falls back to
    DEFAULT_MAX_ACTIVE_PATIENT_LINKS (5) rather than propagating the
    exception. get_platform_settings() (the admin endpoint's own read) is
    NOT covered by this fallback -- an admin should see a real error, not a
    silently-substituted value."""
    from unittest.mock import patch

    import db.repository as db
    from db.models import DEFAULT_MAX_ACTIVE_PATIENT_LINKS

    with patch("db.repositories.platform_settings.get_platform_settings", side_effect=RuntimeError("db down")):
        assert db.get_max_active_patient_links() == DEFAULT_MAX_ACTIVE_PATIENT_LINKS


def test_updated_cap_is_immediately_enforced_by_the_patient_linking_flow(hospital_id):
    import db.repository as db
    from db.repository import TooManyLinkedPatientsError

    resp = client.post("/api/admin/platform-settings", json={"max_active_patient_links": 2}, headers=_HEADERS)
    assert resp.status_code == 200
    try:
        db.create_patient_profile(hospital_id, "5491119990001", "Family Member 1", 30)
        db.create_patient_profile(hospital_id, "5491119990001", "Family Member 2", 8)
        try:
            db.create_patient_profile(hospital_id, "5491119990001", "Family Member 3", 5)
            assert False, "expected TooManyLinkedPatientsError"
        except TooManyLinkedPatientsError:
            pass
    finally:
        client.post("/api/admin/platform-settings", json={"max_active_patient_links": 5}, headers=_HEADERS)
