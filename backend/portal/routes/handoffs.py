# --- Human handoff queue (Section 14.5 follow-up) ---
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from core.whatsapp import WhatsAppClient
from portal.deps import _authenticate, _session_id

router = APIRouter()


@router.get("/api/portal/handoffs")
async def portal_get_handoffs(
    status: str = "open", date: str | None = None, reason: str | None = None,
    authorization: str | None = Header(default=None),
):
    """Item 6 (Spec.md Section 0): date ("YYYY-MM-DD"), when given, scopes
    to requests created that one calendar day -- status filtering
    (open/resolved/all) already existed. Messages page follow-up: reason
    ("system_error"), when given, is the "Errored" tab -- passed with
    status="all" by the frontend so an already-resolved bot error still
    shows up, not just currently-open ones."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    status_filter = None if status == "all" else status
    return JSONResponse({
        "handoffs": db.get_handoff_requests(hospital.id, status=status_filter, date_str=date, reason=reason),
    })


@router.post("/api/portal/handoffs/{handoff_id}/delete")
async def portal_delete_handoff(handoff_id: int, authorization: str | None = Header(default=None)):
    """Item 3: soft-delete only, same convention as bookings above."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    ok = db.soft_delete_handoff(hospital.id, handoff_id)
    if not ok:
        return JSONResponse({"error": "No such handoff request."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "handoffs.delete",
        entity_type="handoff", entity_id=str(handoff_id),
    )
    return JSONResponse({"ok": True})


@router.post("/api/portal/handoffs/{handoff_id}/resolve")
async def portal_resolve_handoff(handoff_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    ok = db.resolve_handoff_request(hospital.id, handoff_id, resolved_by=_session_id(authorization))
    if not ok:
        return JSONResponse({"error": "No such open handoff request."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "handoffs.resolve",
        entity_type="handoff", entity_id=str(handoff_id),
    )
    return JSONResponse({"ok": True})


@router.post("/api/portal/handoffs/bulk-resolve")
async def portal_bulk_resolve_handoffs(payload: dict, authorization: str | None = Header(default=None)):
    """Messages page bulk action. payload = {"handoff_ids": [1, 2, 3]} --
    silently skips any id that isn't this hospital's own, or isn't currently
    open (see bulk_resolve_handoff_requests()'s own docstring); the response
    reports exactly which ids were actually resolved so the frontend can
    show a caller a real count, not an optimistic one."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    handoff_ids = (payload or {}).get("handoff_ids")
    if not isinstance(handoff_ids, list) or not handoff_ids:
        return JSONResponse({"error": "handoff_ids (a non-empty list) is required."}, status_code=400)
    resolved_ids = db.bulk_resolve_handoff_requests(hospital.id, handoff_ids, resolved_by=_session_id(authorization))
    for handoff_id in resolved_ids:
        db.record_audit_log(
            "portal", hospital.id, "tenant portal", "handoffs.resolve",
            entity_type="handoff", entity_id=str(handoff_id),
        )
    return JSONResponse({"ok": True, "resolved": resolved_ids})


@router.post("/api/portal/handoffs/bulk-delete")
async def portal_bulk_delete_handoffs(payload: dict, authorization: str | None = Header(default=None)):
    """Messages page bulk action -- soft-delete only, same convention
    portal_delete_handoff() above already follows."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    handoff_ids = (payload or {}).get("handoff_ids")
    if not isinstance(handoff_ids, list) or not handoff_ids:
        return JSONResponse({"error": "handoff_ids (a non-empty list) is required."}, status_code=400)
    deleted_ids = db.bulk_soft_delete_handoffs(hospital.id, handoff_ids)
    for handoff_id in deleted_ids:
        db.record_audit_log(
            "portal", hospital.id, "tenant portal", "handoffs.delete",
            entity_type="handoff", entity_id=str(handoff_id),
        )
    return JSONResponse({"ok": True, "deleted": deleted_ids})


@router.post("/api/portal/handoffs/{handoff_id}/reply")
async def portal_reply_handoff(handoff_id: int, payload: dict, authorization: str | None = Header(default=None)):
    """Sends a real WhatsApp message back to the patient (does NOT itself
    resolve the handoff -- a staff member may reply more than once before
    marking it done, e.g. asking a clarifying question first).

    Two-way threading follow-up (Spec.md Section 0): now also records the
    reply as an outbound handoff_messages row -- ONLY after the WhatsApp
    send actually succeeds, so the thread never shows a reply that wasn't
    really delivered."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    text = (payload or {}).get("text", "").strip()
    if not text:
        return JSONResponse({"error": "Reply text is required."}, status_code=400)

    matches = [h for h in db.get_handoff_requests(hospital.id, status=None) if h["id"] == handoff_id]
    if not matches:
        return JSONResponse({"error": "No such handoff request."}, status_code=404)
    phone = matches[0]["phone"]

    if not (hospital.whatsapp_phone_number_id and hospital.access_token):
        return JSONResponse({"error": "WhatsApp is not configured for this hospital yet."}, status_code=400)
    wa = WhatsAppClient(phone_number_id=hospital.whatsapp_phone_number_id, access_token=hospital.access_token)
    await wa.send_text(phone, text)
    message = db.add_handoff_message(hospital.id, handoff_id, "outbound", text)
    return JSONResponse({"ok": True, "message": message})


@router.get("/api/portal/handoffs/{handoff_id}/messages")
async def portal_get_handoff_messages(handoff_id: int, authorization: str | None = Header(default=None)):
    """Two-way threading follow-up: the full ordered thread for one handoff
    -- single source of truth for the portal's chat-thread UI."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    matches = [h for h in db.get_handoff_requests(hospital.id, status=None) if h["id"] == handoff_id]
    if not matches:
        return JSONResponse({"error": "No such handoff request."}, status_code=404)
    return JSONResponse({"messages": db.get_handoff_messages(hospital.id, handoff_id)})
