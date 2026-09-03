import logging

from fastapi import APIRouter, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse, Response

import db.repository as db
from core.storage import get_storage
from core.translations import t
from core.translations.my_details import LAB_REPORT_READY_NOTIFICATION
from core.whatsapp import WhatsAppClient
from portal.deps import _authenticate, _session_id

logger = logging.getLogger(__name__)
router = APIRouter()

# WhatsApp menu restructuring: Reports & Prescriptions' "View
# Prescriptions/Lab Reports/Diagnostic Reports" submenu rows filter on
# exactly these -- kept in sync by hand with core/translations/my_details.py's
# REPORTS_MENU_VIEW_* row labels.
_VALID_DOCUMENT_TYPES = {"prescription", "lab_report", "diagnostic_report", "other"}


@router.post("/api/portal/patients/{patient_id}/documents")
async def portal_upload_patient_document(
    patient_id: int, file: UploadFile = File(...), document_type: str = Form("other"),
    appointment_id: int | None = Form(None), authorization: str | None = Header(default=None),
):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    patient = db.get_patient(hospital.id, patient_id)
    if patient is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    if not file.filename:
        return JSONResponse({"error": "A file is required."}, status_code=400)
    if document_type not in _VALID_DOCUMENT_TYPES:
        return JSONResponse({"error": f"Unrecognized document type \"{document_type}\"."}, status_code=400)

    content = await file.read()
    if not content:
        return JSONResponse({"error": "The uploaded file is empty."}, status_code=400)

    storage = get_storage()
    storage_key = storage.upload(
        hospital.id, patient_id, file.filename, content, file.content_type or "application/octet-stream",
    )
    document = db.create_patient_document(
        hospital.id, patient_id, file.filename, storage_key, appointment_id=appointment_id,
        uploaded_by_session_id=_session_id(authorization), document_type=document_type,
    )

    # Lab Test Phase 2 follow-up's report lifecycle: uploading a lab_report
    # against a Lab Test appointment (lab_status is not None) IS the
    # "report_ready" trigger -- no separate staff action, so "report ready"
    # always means an actual report exists. Best-effort: a WhatsApp delivery
    # failure must not turn a successful upload into an error, same posture
    # as portal_cancel_booking()/portal_reschedule_booking() below.
    if document_type == "lab_report" and appointment_id is not None:
        appointment = db.get_appointment(hospital.id, appointment_id)
        if appointment is not None and appointment.lab_status is not None:
            db.set_lab_status(hospital.id, appointment_id, "report_ready")
            if hospital.whatsapp_phone_number_id and hospital.access_token:
                try:
                    wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
                    await wa.send_text(patient["phone"], t(LAB_REPORT_READY_NOTIFICATION, "en"))
                except Exception:
                    logger.exception("Failed to send report-ready notification for appointment %s", appointment_id)

    return JSONResponse({"document": document})


@router.post("/api/portal/patients/{patient_id}/documents/{document_id}/send")
async def portal_send_patient_document(
    patient_id: int, document_id: int, authorization: str | None = Header(default=None),
):
    """Sends the document directly to the patient's own WhatsApp chat.
    Deliberately calls WhatsAppClient directly rather than through
    connectors.py: the Connector interface (connectors.py's module
    docstring) exists to abstract WHERE booking/appointment/doctor data
    lives across data tiers (Tier 1 local DB vs Tier 2 external API vs
    Tier 3 direct DB) -- it has never been the path WhatsApp *sends*
    themselves go through, on any tier. Every existing send (reminders,
    the handoff-reply endpoint, the cancel-with-message endpoint) already
    calls WhatsAppClient directly with the hospital's own credentials,
    regardless of that hospital's data_tier -- sending a message isn't a
    booking-data operation, so there's no tier-specific behavior to
    abstract here. This follows that same established pattern rather than
    introducing a new, inconsistent one."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    patient = db.get_patient(hospital.id, patient_id)
    if patient is None:
        return JSONResponse({"error": "No such patient."}, status_code=404)
    document = db.get_patient_document(hospital.id, document_id)
    if document is None or document["patient_id"] != patient_id:
        return JSONResponse({"error": "No such document."}, status_code=404)

    if not (hospital.whatsapp_phone_number_id and hospital.access_token):
        return JSONResponse({"error": "WhatsApp is not configured for this hospital yet."}, status_code=400)

    storage = get_storage()
    document_url = storage.get_signed_url(document["file_url"], expires_in=3600)

    wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
    sent = await wa.send_document(patient["phone"], document_url, document["file_name"])
    if not sent:
        return JSONResponse(
            {"error": "Couldn't send the document on WhatsApp. Please check the connection and try again."},
            status_code=502,
        )
    db.mark_document_sent_to_whatsapp(hospital.id, document_id)
    return JSONResponse({"ok": True})


@router.get("/api/documents/local/{token:path}")
async def portal_serve_local_document(token: str):
    """Only reachable/meaningful when core/storage.py fell back to
    LocalFileStorage (no S3_BUCKET configured) -- S3Storage's signed URLs
    point directly at S3/R2 and never touch this app at all. No portal
    Bearer-token auth here: the signed, expiring token IS the capability --
    the same way an S3 presigned URL needs no separate auth header either."""
    storage = get_storage()
    if not hasattr(storage, "verify_token"):
        return JSONResponse({"error": "Not found."}, status_code=404)
    storage_key = storage.verify_token(token)
    if storage_key is None:
        return JSONResponse({"error": "This link has expired or is invalid."}, status_code=403)
    content = storage.read(storage_key)
    if content is None:
        return JSONResponse({"error": "Not found."}, status_code=404)
    file_name = storage_key.rsplit("_", 1)[-1]
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
