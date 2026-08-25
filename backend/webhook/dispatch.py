# webhook/dispatch.py
"""
ARCHITECTURE_PLAN.md Phase 4: WA-client cache, Redis-backed (with in-memory
fallback) per-message processing lock, and the actual message dispatch into
flows.handle_incoming() -- split out of the former single core/main.py
module. webhook/routes.py's POST /webhook handler calls into this after
parsing/validating the incoming payload; webhook/cron_routes.py's
/internal/send-reminders also reuses _get_whatsapp_client (one client per
hospital, reused for the life of the process).

HISTORY/SESSIONS are the two module-level singletons every webhook/ file
needs -- defined here since this is where message *processing* (not just
receiving) happens, and re-exported for webhook/routes.py to use directly
for its own audio-message/error-notification session lookups.
"""
import logging
import os
import time

from db.models import Hospital
from connectors import get_connector_for_hospital
import flows
from core.chat_history import get_history
from core.session_store import get_session_store
from core.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)

HISTORY = get_history()
SESSIONS = get_session_store()

_redis = None  # None = not yet checked; False = checked and unreachable; client = available

# In-memory fallback for the per-(hospital, phone) message-processing lock (used when Redis is not available)
_message_locks: dict[str, float] = {}  # "hospital_id:phone" -> lock expiry timestamp

# One WhatsAppClient per hospital, built lazily from that hospital's own DB-stored
# credentials (SPEC Section 12.2) and reused for the life of the process — avoids
# re-creating an httpx.AsyncClient (connection pool) on every message.
#
# IMPORTANT — this cache is keyed by hospital.id only, never invalidated, and
# never re-reads the DB once populated: if a hospital's access_token/app_secret
# row is updated directly in the database (e.g. rotating an expired Meta
# token) while this process is already running, that change is NOT picked up
# until the process restarts. A running process will keep using the OLD
# credentials for that hospital indefinitely — sends will keep failing with
# Meta's 401 even after the DB row is fixed — until you restart it. This is
# the single most likely reason a "I already updated the token in the DB"
# report doesn't actually resolve a 401: the fix is a process restart, not a
# second DB update. Verified live (SPEC Section 0's product-readiness pass):
# a same-process re-fetch after a direct DB update still returns the old
# cached client; only a fresh process picks up the new value.
_wa_clients: dict[int, WhatsAppClient] = {}


def _get_whatsapp_client(hospital: Hospital) -> WhatsAppClient:
    client = _wa_clients.get(hospital.id)
    if client is None:
        client = WhatsAppClient(
            phone_number_id=hospital.whatsapp_phone_number_id,
            access_token=hospital.access_token,
        )
        _wa_clients[hospital.id] = client
    return client


def _get_redis():
    """Same connect-once-and-fall-back pattern as core.chat_history's get_history()/
    core.session_store's get_session_store(): ping once, and if Redis isn't reachable, remember that
    (False) instead of returning a client that will raise on first real command."""
    global _redis
    if _redis is None:
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            try:
                import redis
                client = redis.from_url(redis_url, decode_responses=True)
                client.ping()
                _redis = client
            except Exception:
                _redis = False
        else:
            _redis = False
    return _redis


def _acquire_message_lock(hospital_id: int, phone: str, ttl: int = 15) -> bool:
    """Try to acquire a processing lock for this (hospital, phone) pair. Returns
    True if acquired. Scoped by hospital_id so the same phone number messaging
    two different hospitals can never block itself across them (SPEC Section 12.2)."""
    key_suffix = f"{hospital_id}:{phone}"
    r = _get_redis()
    if r:
        return bool(r.set(f"msg_lock:{key_suffix}", "1", nx=True, ex=ttl))
    # In-memory fallback
    now = time.time()
    expiry = _message_locks.get(key_suffix, 0)
    if now < expiry:
        return False  # Lock still held
    _message_locks[key_suffix] = now + ttl
    return True


def _release_message_lock(hospital_id: int, phone: str):
    key_suffix = f"{hospital_id}:{phone}"
    r = _get_redis()
    if r:
        r.delete(f"msg_lock:{key_suffix}")
    else:
        _message_locks.pop(key_suffix, None)


async def _process_message(
    wa: WhatsAppClient, hospital: Hospital, phone: str, reply: dict,
    provider_user_id: str | None = None, username: str | None = None,
) -> None:
    """Process a single already-parsed incoming message with the (hospital, phone) lock already held."""
    logger.info(
        "Dispatching message from %s (hospital %s), enabled_features=%s: %s",
        phone, hospital.id, hospital.enabled_features, reply,
    )
    HISTORY.add(phone, "user", reply.get("text") or reply.get("title") or f"[{reply.get('type')}]")
    # SPEC Section 12.6.2: resolve this hospital's data_tier to a concrete
    # connector exactly once, here, and hand it down -- flow handlers never
    # look at hospital.data_tier themselves.
    connector = get_connector_for_hospital(hospital)
    # SPEC Section 14.5: flows.py is now the actual conversation entry point
    # (not a lookup returning someone else's handler) -- it builds the IDLE
    # main menu from hospital.enabled_features and internally delegates to
    # core/booking_flow.py's/faq_flow.py's own sub-flow logic once a feature
    # is selected.
    await flows.handle_incoming(
        wa, SESSIONS, phone, hospital.id, reply, hospital.name, connector, hospital.enabled_features,
        feature_labels=hospital.feature_labels,
        closing_message_text=hospital.closing_message_text,
        business_hours_text=hospital.business_hours_text,
        default_language=hospital.default_language,
        language_prompt_enabled=hospital.language_prompt_enabled,
        session_timeout_minutes=hospital.session_timeout_minutes,
        require_patient_confirmation=hospital.require_patient_confirmation,
        privacy_notice_text=hospital.privacy_notice_text,
        provider_user_id=provider_user_id,
        username=username,
        dpdp_consent_required=hospital.dpdp_consent_required,
    )
    logger.info("Flow router returned for %s (hospital %s)", phone, hospital.id)
