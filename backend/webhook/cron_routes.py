# webhook/cron_routes.py
"""
ARCHITECTURE_PLAN.md Phase 4: the two external-cron-triggered endpoints
(reminders, slot top-up) -- split out of the former single core/main.py
module.
"""
import logging

from fastapi import APIRouter, HTTPException, Request

import db.repository as db
from connectors import ConnectorNotImplementedError, get_connector_for_hospital
from core.config import get_settings
from reminders.scheduler import send_reminders
from slots.scheduler import top_up_slots_for_hospital
from webhook.dispatch import _get_whatsapp_client

logger = logging.getLogger(__name__)

_settings = get_settings()
INTERNAL_SECRET = _settings.INTERNAL_SECRET

router = APIRouter()


@router.post("/internal/send-reminders")
async def trigger_reminders(request: Request):
    """Hit by an external cron job (SPEC Section 3.5) — not an in-process scheduler.
    Loops over every active hospital (SPEC Section 12.2), sending each one's
    reminders with its own credentials and its own reminder_offsets_hours."""
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403)

    sent_by_hospital = {}
    for hospital in db.get_active_hospitals():
        # SPEC Section 12.6.2: resolved once per hospital, same as the webhook
        # handler above -- one hospital with no working connector must not
        # stop every other hospital's reminders from sending. The whole
        # per-hospital attempt (dispatch AND the actual send) is guarded,
        # since get_connector_for_hospital() succeeding doesn't mean the
        # connector's methods will -- Tier2Connector/Tier3Connector only
        # raise once a method is actually called, inside send_reminders().
        try:
            connector = get_connector_for_hospital(hospital)
            wa = _get_whatsapp_client(hospital)
            sent_by_hospital[hospital.name] = await send_reminders(wa, hospital.id, hospital.reminder_offsets_hours, connector)
        except ConnectorNotImplementedError:
            logger.error("Hospital %s has no working connector for data_tier -- skipping its reminders", hospital.id)

    return {"sent": sum(sent_by_hospital.values()), "by_hospital": sent_by_hospital}


@router.post("/internal/top-up-slots")
async def trigger_slot_top_up(request: Request):
    """Hit by an external cron job (SPEC Section 12.1.1), same pattern as
    /internal/send-reminders above. Loops every active hospital and extends
    each of its doctors' rolling doctor_slots window forward as days pass."""
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403)

    generated_by_hospital = {
        hospital.name: top_up_slots_for_hospital(hospital.id)
        for hospital in db.get_active_hospitals()
    }
    return {"generated": sum(generated_by_hospital.values()), "by_hospital": generated_by_hospital}
