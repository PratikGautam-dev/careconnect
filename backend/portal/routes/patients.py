from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate, _session_id
from portal.routes.bookings import _appointment_json

router = APIRouter()


@router.get("/api/portal/patients")
async def portal_patients(search: str = "", authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"patients": db.list_patients(hospital.id, search=search)})


# --- Patient detail: demographics, visit history, notes, documents
# (Section 12.10) ---

def _patient_json(p: dict) -> dict:
    return {
        "id": p["id"], "phone": p["phone"], "name": p["name"],
        # Patient identity system (Spec.md Section 0): the permanent,
        # human-readable id (PAT-<hospital short code>-<seq>) -- None only
        # for a patient predating the backfill, which db/init_db.py's
        # _backfill_patient_display_ids() catches up on every startup.
        "patient_display_id": p.get("patient_display_id"),
        "date_of_birth": p.get("date_of_birth"), "gender": p.get("gender"), "address": p.get("address"),
        "created_at": p["created_at"],
        # CareConnect architecture doc alignment (Spec.md Section 0), Section
        # 18's Patient Master state model -- "active" for every patient that
        # predates this column too (db/schema.sql's own default).
        "status": p.get("status", "active"),
    }


@router.get("/api/portal/patients/{patient_id}")
async def portal_patient_detail(patient_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    patient = db.get_patient(hospital.id, patient_id)
    if patient is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)

    visit_history = db.get_patient_visit_history(hospital.id, patient_id)
    notes = db.get_patient_visit_notes(hospital.id, patient_id)
    documents = db.get_patient_documents(hospital.id, patient_id)

    return JSONResponse({
        "patient": _patient_json(patient),
        "visit_history": [_appointment_json(a) for a in visit_history],
        "notes": notes,
        "documents": documents,
    })


@router.post("/api/portal/patients/{patient_id}")
async def portal_update_patient(patient_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    updated = db.update_patient_demographics(
        hospital.id, patient_id,
        date_of_birth=(payload or {}).get("date_of_birth") or None,
        gender=(payload or {}).get("gender") or None,
        address=(payload or {}).get("address") or None,
    )
    if updated is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    return JSONResponse({"patient": _patient_json(updated)})


@router.post("/api/portal/patients/{patient_id}/status")
async def portal_set_patient_status(patient_id: int, payload: dict, authorization: str | None = Header(default=None)):
    """CareConnect architecture doc alignment (Spec.md Section 0), Section
    18: staff-side way to block/reactivate a patient record -- a hospital-
    level fact about the PATIENT, independent of any phone's own link to
    them (db.set_patient_status()'s own docstring). "active" un-blocks."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    status = (payload or {}).get("status")
    if status not in db.PATIENT_STATUSES:
        return JSONResponse({"error": f"status must be one of {db.PATIENT_STATUSES}."}, status_code=400)
    updated = db.set_patient_status(hospital.id, patient_id, status)
    if updated is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    return JSONResponse({"patient": _patient_json(updated)})


@router.post("/api/portal/patients/{patient_id}/notes")
async def portal_add_patient_note(patient_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    if db.get_patient(hospital.id, patient_id) is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)

    note_text = ((payload or {}).get("note_text") or "").strip()
    if not note_text:
        return JSONResponse({"error": "Note text is required."}, status_code=400)
    appointment_id = (payload or {}).get("appointment_id") or None
    doctor_id = (payload or {}).get("doctor_id") or None

    note = db.create_patient_visit_note(
        hospital.id, patient_id, note_text,
        appointment_id=appointment_id, doctor_id=doctor_id,
        created_by_session_id=_session_id(authorization),
    )
    return JSONResponse({"note": note})
