# tests/test_patient_records.py
"""
SPEC Section 12.10: patient records (visit history, notes, document
upload/WhatsApp-send) -- first version, deliberately scoped (no clinical
diagnosis coding, no allergy/condition tracking yet).

Covers:
  - core/storage.py's LocalFileStorage in isolation: upload/read round trip,
    signed-URL token verification (valid, expired, tampered), used as the
    dev/test fallback since no real S3/R2 credentials exist in this
    environment (core/storage.py's own docstring explains the fallback).
  - db/repository.py's new patient-record functions directly.
  - portal/routes/patients.py's and portal/routes/documents.py's new /api/portal/patients/{id}* routes end to end,
    including cross-tenant isolation on every one of them (a hospital's
    session can never see/add/send another hospital's patient data) and the
    "Send to WhatsApp" flow with a mocked WhatsAppClient.send_document (no
    real HTTP call) -- both the success and failure paths.
"""
import os

import pytest

import core.storage as storage
import db.repository as db
from core.whatsapp import WhatsAppClient

os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "mytoken")
os.environ.setdefault("WHATSAPP_APP_SECRET", "appsecret")
os.environ.setdefault("INTERNAL_SECRET", "internalsecret")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "test@calendar")
os.environ.setdefault("GOOGLE_CALENDAR_OWNER_EMAIL", "test@test.com")
os.environ.setdefault("PORTAL_SECRET", "test-portal-secret")

from backend.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_local_storage(tmp_path):
    """core/storage.py's get_storage() is a module-level singleton (same
    reason core/session_store.py's session store is one) -- tests need their own
    throwaway directory instead of ever touching the real LOCAL_STORAGE_DIR
    or leaking files between tests."""
    storage.reset_storage_for_tests(tmp_path)
    yield


def _set_hospital_creds(hospital_id: int, *, password: str, phone_number_id: str, access_token: str) -> None:
    h = db.get_hospital(hospital_id)
    db.update_hospital(
        hospital_id, name=h.name, whatsapp_phone_number_id=phone_number_id, access_token=access_token,
        app_secret=h.app_secret, timezone=h.timezone, welcome_message_text=h.welcome_message_text,
        reminder_offsets_hours=h.reminder_offsets_hours, reminder_template_name=h.reminder_template_name,
        data_tier=h.data_tier, external_api_base_url=h.external_api_base_url,
        external_api_key=h.external_api_key, portal_password_hash=db.hash_portal_password(password),
        enabled_features=h.enabled_features,
    )


def _login(password: str) -> str:
    resp = client.post("/api/portal/login", json={"password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_appointment(hospital_id: int, doctor_id: str, department_id: str, phone: str, patient_name=None):
    from datetime import datetime
    slot = db.get_slots(hospital_id, doctor_id)[0]
    scheduled_at = datetime.fromisoformat(slot["id"])
    return db.create_appointment(hospital_id, phone, department_id, doctor_id, scheduled_at, patient_name=patient_name)


@pytest.fixture
def two_hospitals(hospital_id, second_hospital_id):
    _set_hospital_creds(hospital_id, password="hospital-a-pw", phone_number_id="hospital-a-phone", access_token="hospital-a-token")
    _set_hospital_creds(second_hospital_id, password="hospital-b-pw", phone_number_id="hospital-b-phone", access_token="hospital-b-token")
    return {
        "a": {"id": hospital_id, "token": _login("hospital-a-pw"), "doctor_id": "doc_card_1", "department_id": "cardiology"},
        "b": {"id": second_hospital_id, "token": _login("hospital-b-pw"), "doctor_id": "t2_doc_neuro_1", "department_id": "t2_neurology"},
    }


@pytest.fixture
def patient_a(two_hospitals):
    """A real patient row for hospital A, created via a real booking (same
    path production data comes from)."""
    a = two_hospitals["a"]
    _create_appointment(a["id"], a["doctor_id"], a["department_id"], "5491112223333", patient_name="Rahul Sharma")
    patients = db.list_patients(a["id"])
    return next(p for p in patients if p["phone"] == "5491112223333")


@pytest.fixture
def fake_whatsapp_document_send(monkeypatch):
    """Records every WhatsAppClient.send_document() call (which hospital's
    credentials, which phone/url/filename) and lets each test control the
    return value (success/failure) per call via a mutable list of results."""
    calls = []
    results = iter([True] * 1000)  # tests can monkeypatch `results` via the returned dict if they need failures

    async def fake_send_document(self, to, document_url, filename, caption=None):
        calls.append({
            "phone_number_id": self._phone_number_id, "access_token": self._token,
            "to": to, "document_url": document_url, "filename": filename,
        })
        return next(results)

    monkeypatch.setattr(WhatsAppClient, "send_document", fake_send_document)
    return {"calls": calls, "results": results}


# --- core/storage.py: LocalFileStorage in isolation ---


def _token_from_url(url: str) -> str:
    """The token itself contains '/' (it's built from a storage_key that
    does, e.g. "patients/1/42/xxx_report.pdf") -- strip the fixed route
    prefix rather than splitting on the last '/', which would truncate it."""
    return url.removeprefix("/api/documents/local/")


def test_local_storage_upload_and_read_round_trip(tmp_path):
    store = storage.LocalFileStorage(tmp_path, "test-secret")
    key = store.upload(1, 42, "report.pdf", b"pdf-bytes-here", "application/pdf")
    assert key.startswith("patients/1/42/")
    assert key.endswith("_report.pdf")
    assert store.read(key) == b"pdf-bytes-here"


def test_local_storage_signed_url_verifies_and_serves(tmp_path):
    store = storage.LocalFileStorage(tmp_path, "test-secret")
    key = store.upload(1, 42, "report.pdf", b"data", "application/pdf")
    url = store.get_signed_url(key, expires_in=3600)
    token = _token_from_url(url)
    assert store.verify_token(token) == key


def test_local_storage_signed_url_rejects_expired_token(tmp_path, monkeypatch):
    store = storage.LocalFileStorage(tmp_path, "test-secret")
    key = store.upload(1, 42, "report.pdf", b"data", "application/pdf")

    now = [1_000_000.0]
    monkeypatch.setattr(storage.time, "time", lambda: now[0])
    url = store.get_signed_url(key, expires_in=60)
    token = _token_from_url(url)
    assert store.verify_token(token) == key  # valid right after minting

    now[0] += 61  # advance past expiry
    assert store.verify_token(token) is None


def test_local_storage_signed_url_rejects_tampered_token(tmp_path):
    store = storage.LocalFileStorage(tmp_path, "test-secret")
    key = store.upload(1, 42, "report.pdf", b"data", "application/pdf")
    url = store.get_signed_url(key, expires_in=3600)
    token = _token_from_url(url)
    assert store.verify_token(token) == key  # sanity: the real token is valid before we tamper with it

    storage_key, expires_at, sig = token.rsplit(".", 2)
    tampered = f"{storage_key}-tampered.{expires_at}.{sig}"
    assert store.verify_token(tampered) is None

    # A signature minted under a DIFFERENT secret must also fail.
    other_store = storage.LocalFileStorage(tmp_path, "different-secret")
    other_token = other_store._sign(storage_key, int(expires_at))
    assert store.verify_token(other_token) is None


def test_local_storage_read_rejects_path_traversal(tmp_path):
    store = storage.LocalFileStorage(tmp_path, "test-secret")
    assert store.read("../../etc/passwd") is None


# --- db/repository.py: patient-record functions directly ---


def test_get_patient_scoped_to_hospital(two_hospitals, patient_a):
    a, b = two_hospitals["a"], two_hospitals["b"]
    assert db.get_patient(a["id"], patient_a["id"]) is not None
    assert db.get_patient(b["id"], patient_a["id"]) is None  # wrong hospital


def test_update_patient_demographics(two_hospitals, patient_a):
    a = two_hospitals["a"]
    updated = db.update_patient_demographics(a["id"], patient_a["id"], "1990-05-15", "female", "12 MG Road")
    assert updated["date_of_birth"] == "1990-05-15"
    assert updated["gender"] == "female"
    assert updated["address"] == "12 MG Road"


def test_visit_history_returns_appointments_most_recent_first(two_hospitals, patient_a):
    a = two_hospitals["a"]
    history = db.get_patient_visit_history(a["id"], patient_a["id"])
    assert len(history) == 1
    assert history[0].doctor_name == "Dr. Anjali Rao"


def test_create_visit_note_populates_audit_fields(two_hospitals, patient_a):
    a = two_hospitals["a"]
    note = db.create_patient_visit_note(
        a["id"], patient_a["id"], "Patient reports mild chest discomfort.",
        appointment_id=None, doctor_id=a["doctor_id"], created_by_session_id="abc123session",
    )
    assert note["note_text"] == "Patient reports mild chest discomfort."
    assert note["created_by_session_id"] == "abc123session"
    assert note["created_at"] is not None

    fetched = db.get_patient_visit_notes(a["id"], patient_a["id"])
    assert len(fetched) == 1
    assert fetched[0]["doctor_name"] == "Dr. Anjali Rao"


def test_create_and_send_document_repository_level(two_hospitals, patient_a):
    a = two_hospitals["a"]
    doc = db.create_patient_document(
        a["id"], patient_a["id"], "bloodwork.pdf", "patients/1/1/abc_bloodwork.pdf",
        uploaded_by_session_id="sess1",
    )
    assert doc["sent_to_whatsapp_at"] is None
    assert db.mark_document_sent_to_whatsapp(a["id"], doc["id"]) is True

    fetched = db.get_patient_document(a["id"], doc["id"])
    assert fetched["sent_to_whatsapp_at"] is not None


def test_mark_document_sent_scoped_to_hospital(two_hospitals, patient_a):
    a, b = two_hospitals["a"], two_hospitals["b"]
    doc = db.create_patient_document(a["id"], patient_a["id"], "x.pdf", "patients/1/1/x.pdf")
    assert db.mark_document_sent_to_whatsapp(b["id"], doc["id"]) is False  # wrong hospital


# --- portal/routes/patients.py: patient detail route ---


def test_patient_detail_returns_demographics_history_notes_documents(two_hospitals, patient_a):
    a = two_hospitals["a"]
    db.update_patient_demographics(a["id"], patient_a["id"], "1990-01-01", "male", "1 Test St")
    db.create_patient_visit_note(a["id"], patient_a["id"], "General note.")
    db.create_patient_document(a["id"], patient_a["id"], "doc.pdf", "some/key.pdf")

    resp = client.get(f"/api/portal/patients/{patient_a['id']}", headers=_auth(a["token"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["patient"]["date_of_birth"] == "1990-01-01"
    assert len(body["visit_history"]) == 1
    assert len(body["notes"]) == 1
    assert len(body["documents"]) == 1


def test_patient_detail_404_for_unknown_id(two_hospitals):
    a = two_hospitals["a"]
    resp = client.get("/api/portal/patients/999999", headers=_auth(a["token"]))
    assert resp.status_code == 404


def test_update_demographics_via_api(two_hospitals, patient_a):
    a = two_hospitals["a"]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}", json={"date_of_birth": "1985-03-20", "gender": "male", "address": ""},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["patient"]["date_of_birth"] == "1985-03-20"
    assert resp.json()["patient"]["address"] is None


# --- portal/routes/patients.py: notes ---


def test_add_note_via_api_populates_session_id(two_hospitals, patient_a):
    a = two_hospitals["a"]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/notes", json={"note_text": "Follow-up in 2 weeks."},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200
    note = resp.json()["note"]
    assert note["note_text"] == "Follow-up in 2 weeks."
    assert note["created_by_session_id"] is not None
    assert len(note["created_by_session_id"]) == 16  # sha256 truncated to 16 hex chars


def test_add_note_requires_nonempty_text(two_hospitals, patient_a):
    a = two_hospitals["a"]
    resp = client.post(f"/api/portal/patients/{patient_a['id']}/notes", json={"note_text": "   "}, headers=_auth(a["token"]))
    assert resp.status_code == 400


def test_add_note_tied_to_appointment(two_hospitals, patient_a):
    a = two_hospitals["a"]
    visit = db.get_patient_visit_history(a["id"], patient_a["id"])[0]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/notes",
        json={"note_text": "Discussed results.", "appointment_id": visit.id, "doctor_id": a["doctor_id"]},
        headers=_auth(a["token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["note"]["appointment_id"] == visit.id


# --- portal/routes/documents.py: document upload ---


def test_upload_document_creates_row_and_stores_content(two_hospitals, patient_a):
    a = two_hospitals["a"]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("bloodwork.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert resp.status_code == 200
    doc = resp.json()["document"]
    assert doc["file_name"] == "bloodwork.pdf"

    store = storage.get_storage()
    fetched = db.get_patient_document(a["id"], doc["id"])
    assert store.read(fetched["file_url"]) == b"%PDF-1.4 fake content"


def test_upload_empty_file_rejected(two_hospitals, patient_a):
    a = two_hospitals["a"]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400


# --- portal/routes/documents.py: send to WhatsApp ---


def test_send_document_uses_correct_hospital_credentials(two_hospitals, patient_a, fake_whatsapp_document_send):
    a = two_hospitals["a"]
    upload_resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("report.pdf", b"content", "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    resp = client.post(f"/api/portal/patients/{patient_a['id']}/documents/{doc_id}/send", headers=_auth(a["token"]))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    calls = fake_whatsapp_document_send["calls"]
    assert len(calls) == 1
    assert calls[0]["phone_number_id"] == "hospital-a-phone"
    assert calls[0]["access_token"] == "hospital-a-token"
    assert calls[0]["to"] == patient_a["phone"]
    assert calls[0]["filename"] == "report.pdf"

    fetched = db.get_patient_document(a["id"], doc_id)
    assert fetched["sent_to_whatsapp_at"] is not None


def test_send_document_failure_does_not_crash_and_shows_error(two_hospitals, patient_a, monkeypatch):
    a = two_hospitals["a"]
    upload_resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("report.pdf", b"content", "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    async def failing_send_document(self, to, document_url, filename, caption=None):
        return False  # e.g. Meta API rejected the request

    monkeypatch.setattr(WhatsAppClient, "send_document", failing_send_document)

    resp = client.post(f"/api/portal/patients/{patient_a['id']}/documents/{doc_id}/send", headers=_auth(a["token"]))
    assert resp.status_code == 502
    assert "error" in resp.json()

    fetched = db.get_patient_document(a["id"], doc_id)
    assert fetched["sent_to_whatsapp_at"] is None  # not marked sent on failure


def test_send_document_network_exception_does_not_crash(two_hospitals, patient_a, monkeypatch):
    """The endpoint itself must survive send_document() raising -- but
    send_document() already catches httpx errors internally and returns
    False (core/whatsapp.py), so this proves that contract end to end
    through the portal route too."""
    a = two_hospitals["a"]
    upload_resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("report.pdf", b"content", "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    import httpx as httpx_module

    async def raising_post(*args, **kwargs):
        raise httpx_module.ConnectError("simulated network failure")

    monkeypatch.setattr("core.whatsapp.httpx.AsyncClient.post", raising_post)

    resp = client.post(f"/api/portal/patients/{patient_a['id']}/documents/{doc_id}/send", headers=_auth(a["token"]))
    assert resp.status_code == 502


# --- Local document-serving endpoint ---


def test_local_document_endpoint_serves_valid_token(two_hospitals, patient_a):
    a = two_hospitals["a"]
    upload_resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("report.pdf", b"the real bytes", "application/pdf")},
    )
    doc = upload_resp.json()["document"]
    store = storage.get_storage()
    url = store.get_signed_url(doc["file_url"])
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.content == b"the real bytes"


def test_local_document_endpoint_rejects_invalid_token(two_hospitals, patient_a):
    resp = client.get("/api/documents/local/not-a-real-token")
    assert resp.status_code == 403


# --- Cross-tenant isolation: the whole surface, per the audit's own pattern ---


def test_hospital_b_cannot_view_hospital_a_patient(two_hospitals, patient_a):
    b = two_hospitals["b"]
    resp = client.get(f"/api/portal/patients/{patient_a['id']}", headers=_auth(b["token"]))
    assert resp.status_code == 404


def test_hospital_b_cannot_update_hospital_a_patient_demographics(two_hospitals, patient_a):
    b = two_hospitals["b"]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}", json={"gender": "other"}, headers=_auth(b["token"]),
    )
    assert resp.status_code == 404
    assert db.get_patient(two_hospitals["a"]["id"], patient_a["id"])["gender"] is None


def test_hospital_b_cannot_add_note_to_hospital_a_patient(two_hospitals, patient_a):
    b = two_hospitals["b"]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/notes", json={"note_text": "malicious note"},
        headers=_auth(b["token"]),
    )
    assert resp.status_code == 404
    assert db.get_patient_visit_notes(two_hospitals["a"]["id"], patient_a["id"]) == []


def test_hospital_b_cannot_upload_document_to_hospital_a_patient(two_hospitals, patient_a):
    b = two_hospitals["b"]
    resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(b["token"]),
        files={"file": ("malicious.pdf", b"content", "application/pdf")},
    )
    assert resp.status_code == 404
    assert db.get_patient_documents(two_hospitals["a"]["id"], patient_a["id"]) == []


def test_hospital_b_cannot_send_hospital_a_patient_document(two_hospitals, patient_a, fake_whatsapp_document_send):
    a, b = two_hospitals["a"], two_hospitals["b"]
    upload_resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("report.pdf", b"content", "application/pdf")},
    )
    doc_id = upload_resp.json()["document"]["id"]

    resp = client.post(f"/api/portal/patients/{patient_a['id']}/documents/{doc_id}/send", headers=_auth(b["token"]))
    assert resp.status_code == 404
    assert fake_whatsapp_document_send["calls"] == []


def test_hospital_b_cannot_send_document_by_guessing_id_under_own_patient(two_hospitals, patient_a, fake_whatsapp_document_send):
    """A subtler isolation gap: even a hospital B patient_id/document_id pair
    combo where document_id belongs to hospital A but patient_id is one
    hospital B actually owns must not leak hospital A's document."""
    a, b = two_hospitals["a"], two_hospitals["b"]
    _create_appointment(b["id"], b["doctor_id"], b["department_id"], "5490009999", patient_name="B Patient")
    patient_b = next(p for p in db.list_patients(b["id"]) if p["phone"] == "5490009999")

    upload_resp = client.post(
        f"/api/portal/patients/{patient_a['id']}/documents", headers=_auth(a["token"]),
        files={"file": ("report.pdf", b"content", "application/pdf")},
    )
    doc_id_belongs_to_a = upload_resp.json()["document"]["id"]

    resp = client.post(
        f"/api/portal/patients/{patient_b['id']}/documents/{doc_id_belongs_to_a}/send", headers=_auth(b["token"]),
    )
    assert resp.status_code == 404
    assert fake_whatsapp_document_send["calls"] == []


def test_hospital_b_cannot_view_hospital_a_patients_notes_via_list_endpoint(two_hospitals, patient_a):
    a, b = two_hospitals["a"], two_hospitals["b"]
    db.create_patient_visit_note(a["id"], patient_a["id"], "Private note about patient A.")
    resp = client.get("/api/portal/patients", headers=_auth(b["token"]))
    assert resp.status_code == 200
    assert all(p["phone"] != patient_a["phone"] for p in resp.json()["patients"])
