# db/repositories/patient_records.py
"""Patient visit history, visit notes, and document uploads (Section
12.10). Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime
from typing import cast

from sqlalchemy import insert, select, update
from sqlalchemy.engine import CursorResult

from db.connection import get_session
from db.models import Appointment, _row_to_appointment
from db.orm_models import AppointmentRow, DoctorRow, PatientDocument, PatientRow, PatientVisitNote
from db.repositories.appointments import _appointment_select_stmt

def get_patient_visit_history(hospital_id: int, patient_id: int) -> list[Appointment]:
    """Every appointment for this patient (any status, most recent first) --
    reuses the exact same `appointments` data the rest of the app already
    has; no new table needed for "visit history" itself, only for notes/
    documents attached to a visit. Returns [] for an unknown/foreign
    patient_id rather than raising -- callers that need to distinguish
    "no visits" from "no such patient" should call get_patient() first.

    Now ORM-based, reusing appointments.py's _appointment_select_stmt() --
    that domain's migration landed, closing the deferral this function's
    docstring used to describe."""
    session = get_session()
    patient = session.execute(
        select(PatientRow.phone).where(PatientRow.hospital_id == hospital_id, PatientRow.id == patient_id)
    ).first()
    if patient is None:
        return []
    rows = session.execute(
        _appointment_select_stmt()
        .where(AppointmentRow.hospital_id == hospital_id, AppointmentRow.phone == patient.phone)
        .order_by(AppointmentRow.scheduled_at.desc())
    ).all()
    return [_row_to_appointment(r._mapping) for r in rows]


def create_patient_visit_note(
    hospital_id: int, patient_id: int, note_text: str,
    appointment_id: int | None = None, doctor_id: str | None = None, created_by_session_id: str | None = None,
) -> dict:
    session = get_session()
    row = session.execute(
        insert(PatientVisitNote)
        .values(
            hospital_id=hospital_id, patient_id=patient_id, appointment_id=appointment_id,
            doctor_id=doctor_id, note_text=note_text, created_by_session_id=created_by_session_id,
        )
        .returning(PatientVisitNote.id, PatientVisitNote.created_at)
    ).first()
    assert row is not None  # INSERT ... RETURNING always returns the inserted row
    session.commit()
    return {
        "id": row.id, "patient_id": patient_id, "appointment_id": appointment_id, "doctor_id": doctor_id,
        "note_text": note_text, "created_at": row.created_at, "created_by_session_id": created_by_session_id,
    }


def get_patient_visit_notes(hospital_id: int, patient_id: int) -> list[dict]:
    """Most recent first. Includes the doctor's name (not just id) so the
    portal can render it directly without a second lookup."""
    session = get_session()
    rows = session.execute(
        select(
            PatientVisitNote.id, PatientVisitNote.patient_id, PatientVisitNote.appointment_id,
            PatientVisitNote.doctor_id, DoctorRow.name.label("doctor_name"),
            PatientVisitNote.note_text, PatientVisitNote.created_at, PatientVisitNote.created_by_session_id,
        )
        .outerjoin(DoctorRow, DoctorRow.id == PatientVisitNote.doctor_id)
        .where(PatientVisitNote.hospital_id == hospital_id, PatientVisitNote.patient_id == patient_id)
        .order_by(PatientVisitNote.created_at.desc())
    ).all()
    return [dict(r._mapping) for r in rows]


def get_patient_visit_notes_by_doctor(hospital_id: int, patient_id: int, doctor_id: str) -> list[dict]:
    """Doctor-portal follow-up: the /doctor/patients/[id] page's own note
    history -- only notes THIS doctor wrote (PatientVisitNote.doctor_id is
    set on every note added via /api/doctor/appointments/{id}/notes), not
    every note any staff member has ever added for this patient. Same
    "personalised, not just filtered" scoping the rest of the doctor
    portal already applies to appointments/patients."""
    session = get_session()
    rows = session.execute(
        select(
            PatientVisitNote.id, PatientVisitNote.patient_id, PatientVisitNote.appointment_id,
            PatientVisitNote.doctor_id, DoctorRow.name.label("doctor_name"),
            PatientVisitNote.note_text, PatientVisitNote.created_at, PatientVisitNote.created_by_session_id,
        )
        .outerjoin(DoctorRow, DoctorRow.id == PatientVisitNote.doctor_id)
        .where(
            PatientVisitNote.hospital_id == hospital_id, PatientVisitNote.patient_id == patient_id,
            PatientVisitNote.doctor_id == doctor_id,
        )
        .order_by(PatientVisitNote.created_at.desc())
    ).all()
    return [dict(r._mapping) for r in rows]


def create_patient_document(
    hospital_id: int, patient_id: int, file_name: str, file_url: str,
    appointment_id: int | None = None, uploaded_by_session_id: str | None = None,
) -> dict:
    session = get_session()
    row = session.execute(
        insert(PatientDocument)
        .values(
            hospital_id=hospital_id, patient_id=patient_id, appointment_id=appointment_id,
            file_name=file_name, file_url=file_url, uploaded_by_session_id=uploaded_by_session_id,
        )
        .returning(PatientDocument.id, PatientDocument.uploaded_at)
    ).first()
    assert row is not None  # INSERT ... RETURNING always returns the inserted row
    session.commit()
    return {
        "id": row.id, "patient_id": patient_id, "appointment_id": appointment_id, "file_name": file_name,
        "file_url": file_url, "uploaded_at": row.uploaded_at, "uploaded_by_session_id": uploaded_by_session_id,
        "sent_to_whatsapp_at": None,
    }


def get_patient_documents(hospital_id: int, patient_id: int) -> list[dict]:
    session = get_session()
    rows = session.execute(
        select(
            PatientDocument.id, PatientDocument.patient_id, PatientDocument.appointment_id,
            PatientDocument.file_name, PatientDocument.file_url, PatientDocument.uploaded_at,
            PatientDocument.uploaded_by_session_id, PatientDocument.sent_to_whatsapp_at,
        )
        .where(PatientDocument.hospital_id == hospital_id, PatientDocument.patient_id == patient_id)
        .order_by(PatientDocument.uploaded_at.desc())
    ).all()
    return [dict(r._mapping) for r in rows]


def get_patient_document(hospital_id: int, document_id: int) -> dict | None:
    """The ownership check portal/routes/documents.py's send-to-WhatsApp and
    download/signed-URL routes both use before touching storage."""
    session = get_session()
    row = session.execute(
        select(
            PatientDocument.id, PatientDocument.patient_id, PatientDocument.appointment_id,
            PatientDocument.file_name, PatientDocument.file_url, PatientDocument.uploaded_at,
            PatientDocument.uploaded_by_session_id, PatientDocument.sent_to_whatsapp_at,
        )
        .where(PatientDocument.hospital_id == hospital_id, PatientDocument.id == document_id)
    ).first()
    return dict(row._mapping) if row else None


def mark_document_sent_to_whatsapp(hospital_id: int, document_id: int) -> bool:
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(PatientDocument)
        .where(PatientDocument.hospital_id == hospital_id, PatientDocument.id == document_id)
        .values(sent_to_whatsapp_at=datetime.now().isoformat())
    ))
    session.commit()
    return result.rowcount > 0


