# db/repositories/patient_records.py
"""Patient visit history, visit notes, and document uploads (Section
12.10). Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime

from db.connection import get_connection
from db.models import Appointment, _APPOINTMENT_SELECT, _row_to_appointment

def get_patient_visit_history(hospital_id: int, patient_id: int) -> list[Appointment]:
    """Every appointment for this patient (any status, most recent first) --
    reuses the exact same `appointments` data the rest of the app already
    has; no new table needed for "visit history" itself, only for notes/
    documents attached to a visit. Returns [] for an unknown/foreign
    patient_id rather than raising -- callers that need to distinguish
    "no visits" from "no such patient" should call get_patient() first."""
    conn = get_connection()
    patient = conn.execute(
        "SELECT phone FROM patients WHERE hospital_id = ? AND id = ?", (hospital_id, patient_id),
    ).fetchone()
    if patient is None:
        return []
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.phone = ? ORDER BY a.scheduled_at DESC",
        (hospital_id, patient["phone"]),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def create_patient_visit_note(
    hospital_id: int, patient_id: int, note_text: str,
    appointment_id: int | None = None, doctor_id: str | None = None, created_by_session_id: str | None = None,
) -> dict:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO patient_visit_notes "
        "(hospital_id, patient_id, appointment_id, doctor_id, note_text, created_by_session_id) "
        "VALUES (?, ?, ?, ?, ?, ?) RETURNING id, created_at",
        (hospital_id, patient_id, appointment_id, doctor_id, note_text, created_by_session_id),
    )
    row = cur.fetchone()
    conn.commit()
    return {
        "id": row["id"], "patient_id": patient_id, "appointment_id": appointment_id, "doctor_id": doctor_id,
        "note_text": note_text, "created_at": row["created_at"], "created_by_session_id": created_by_session_id,
    }


def get_patient_visit_notes(hospital_id: int, patient_id: int) -> list[dict]:
    """Most recent first. Includes the doctor's name (not just id) so the
    portal can render it directly without a second lookup."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT n.id, n.patient_id, n.appointment_id, n.doctor_id, doc.name AS doctor_name, "
        "n.note_text, n.created_at, n.created_by_session_id "
        "FROM patient_visit_notes n LEFT JOIN doctors doc ON doc.id = n.doctor_id "
        "WHERE n.hospital_id = ? AND n.patient_id = ? ORDER BY n.created_at DESC",
        (hospital_id, patient_id),
    ).fetchall()
    return [dict(r) for r in rows]


def create_patient_document(
    hospital_id: int, patient_id: int, file_name: str, file_url: str,
    appointment_id: int | None = None, uploaded_by_session_id: str | None = None,
) -> dict:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO patient_documents "
        "(hospital_id, patient_id, appointment_id, file_name, file_url, uploaded_by_session_id) "
        "VALUES (?, ?, ?, ?, ?, ?) RETURNING id, uploaded_at",
        (hospital_id, patient_id, appointment_id, file_name, file_url, uploaded_by_session_id),
    )
    row = cur.fetchone()
    conn.commit()
    return {
        "id": row["id"], "patient_id": patient_id, "appointment_id": appointment_id, "file_name": file_name,
        "file_url": file_url, "uploaded_at": row["uploaded_at"], "uploaded_by_session_id": uploaded_by_session_id,
        "sent_to_whatsapp_at": None,
    }


def get_patient_documents(hospital_id: int, patient_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, patient_id, appointment_id, file_name, file_url, uploaded_at, "
        "uploaded_by_session_id, sent_to_whatsapp_at FROM patient_documents "
        "WHERE hospital_id = ? AND patient_id = ? ORDER BY uploaded_at DESC",
        (hospital_id, patient_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_patient_document(hospital_id: int, document_id: int) -> dict | None:
    """The ownership check portal/routes/documents.py's send-to-WhatsApp and
    download/signed-URL routes both use before touching storage."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, patient_id, appointment_id, file_name, file_url, uploaded_at, "
        "uploaded_by_session_id, sent_to_whatsapp_at FROM patient_documents "
        "WHERE hospital_id = ? AND id = ?",
        (hospital_id, document_id),
    ).fetchone()
    return dict(row) if row else None


def mark_document_sent_to_whatsapp(hospital_id: int, document_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE patient_documents SET sent_to_whatsapp_at = ? WHERE hospital_id = ? AND id = ?",
        (datetime.now().isoformat(), hospital_id, document_id),
    )
    if cur.rowcount == 0:
        return False
    conn.commit()
    return True


