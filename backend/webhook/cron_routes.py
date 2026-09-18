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
from core.redis_client import get_redis
from db.repositories.handoffs import DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS
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


@router.post("/internal/auto-resolve-handoffs")
async def trigger_handoff_auto_resolve(request: Request):
    """Messages page follow-up: hit by an external cron job, same pattern as
    /internal/send-reminders/top-up-slots above. Auto-resolves every OPEN
    handoff with no activity from either side past each hospital's own
    handoff_auto_resolve_hours (or DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS if
    unset) -- see db.auto_resolve_stale_handoffs()'s own docstring for what
    "no activity" means."""
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403)

    resolved_by_hospital = {
        hospital.name: len(db.auto_resolve_stale_handoffs(
            hospital.id, hospital.handoff_auto_resolve_hours or DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS,
        ))
        for hospital in db.get_active_hospitals()
    }
    return {"resolved": sum(resolved_by_hospital.values()), "by_hospital": resolved_by_hospital}


# Auto-checkout's own lock key/TTL -- guards against two overlapping runs
# (a cron provider retry, or two schedules pointing at this endpoint by
# mistake) both processing the same overdue records at once. 5 minutes
# comfortably covers how long even a slow run should take across every
# hospital; if a run ever legitimately took longer, letting the NEXT tick
# through once the lock expires is safer than a stuck lock blocking every
# future run forever.
_AUTO_CHECKOUT_LOCK_KEY = "auto_checkout:running"
_AUTO_CHECKOUT_LOCK_TTL_SECONDS = 300


@router.post("/internal/auto-checkout")
async def trigger_auto_checkout(request: Request):
    """Hit by an external cron job every few minutes (SPEC: attendance
    auto-checkout follow-up) -- NOT a per-hospital loop like the endpoints
    above, since this needs no per-hospital external API credentials: one
    global query (db.auto_checkout_overdue()) finds every still-open
    attendance record across every hospital whose own deadline (that staff
    member's shift end + their hospital's grace period) has passed, and
    closes each one out. See that function's own docstring for why a
    single hospital-wide clock time can't do this correctly and why a
    per-staff-shift computation is needed instead.

    Redis-locked (get_redis() -- optional everywhere else in this codebase,
    same posture here: proceeds without the lock if Redis is unreachable,
    since db.auto_checkout_overdue()'s own conditional UPDATE is a second,
    independent guard against double-processing any one record)."""
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403)

    redis_client = get_redis()
    lock_acquired = True
    if redis_client is not None:
        lock_acquired = bool(redis_client.set(_AUTO_CHECKOUT_LOCK_KEY, "1", nx=True, ex=_AUTO_CHECKOUT_LOCK_TTL_SECONDS))
    if not lock_acquired:
        return {"skipped": "already running"}

    try:
        closed = db.auto_checkout_overdue()
    finally:
        if redis_client is not None:
            redis_client.delete(_AUTO_CHECKOUT_LOCK_KEY)

    return {"closed": len(closed), "records": closed}
