import json
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # must run before os.environ[...] reads below, or db.init_db()'s env reads

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

import db.repository as db
from admin.onboarding import router as onboarding_router
from core.booking_flow import handle_incoming
from core.history import get_history, get_session_store
from core.whatsapp import WhatsAppClient, extract_phone_number_id, parse_incoming_message, validate_webhook_signature
from db.init_db import init_db
from reminders.scheduler import send_reminders
from slots.scheduler import top_up_slots_for_hospital

# uvicorn only configures its own "uvicorn"/"uvicorn.error"/"uvicorn.access" loggers
# (see uvicorn.config.LOGGING_CONFIG) — it never touches the root logger. Every logger
# in this app (core.whatsapp, core.main, ...) propagates up to the root logger instead,
# which without this call has no handler and falls back to Python's "last resort"
# handler (WARNING+ only) — so logger.info(...) calls anywhere in the app would be
# silently invisible even though the logging calls themselves are correct.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)

HISTORY = get_history()
SESSIONS = get_session_store()
# Creates the schema + seeds the one real hospital from .env if not already present
# (idempotent, safe on every startup — SPEC Section 12.6 Tier 1).
init_db()

VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")

_redis = None  # None = not yet checked; False = checked and unreachable; client = available

# In-memory fallback for the per-(hospital, phone) message-processing lock (used when Redis is not available)
_message_locks: dict[str, float] = {}  # "hospital_id:phone" -> lock expiry timestamp

# One WhatsAppClient per hospital, built lazily from that hospital's own DB-stored
# credentials (SPEC Section 12.2) and reused for the life of the process — avoids
# re-creating an httpx.AsyncClient (connection pool) on every message.
_wa_clients: dict[int, WhatsAppClient] = {}


def _get_whatsapp_client(hospital: db.Hospital) -> WhatsAppClient:
    client = _wa_clients.get(hospital.id)
    if client is None:
        client = WhatsAppClient(
            phone_number_id=hospital.whatsapp_phone_number_id,
            access_token=hospital.access_token,
        )
        _wa_clients[hospital.id] = client
    return client


def _get_redis():
    """Same connect-once-and-fall-back pattern as core.history's get_history()/
    get_session_store(): ping once, and if Redis isn't reachable, remember that
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(onboarding_router)


@app.get("/")
async def health():
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.body()

    # Covers: invalid JSON body (json.JSONDecodeError, a ValueError subclass),
    # valid JSON that isn't the expected dict-of-dicts shape (a list/string/number
    # anywhere in the payload -> TypeError on subscripting), and payloads missing
    # expected keys/indices (KeyError/IndexError) — e.g. a message type Meta added
    # that we don't parse a field for, a malformed test payload, etc. None of these
    # should crash the webhook handler; Meta gets a 200 either way since there's
    # nothing to usefully retry for a payload shape we don't understand.
    try:
        data = json.loads(body)
        entry = data["entry"][0]
        change = entry["changes"][0]["value"]

        # SPEC Section 12.2: resolve which hospital this message is *for* (the
        # WhatsApp number that received it, from `metadata` — not the sender's
        # number, which is `message["from"]` below) BEFORE trusting/validating
        # anything else in the payload. This is a structural read of routing
        # metadata only, not "processing the message" — nothing here acts on the
        # message content, sends anything, or touches booking/session state; that
        # all happens further down, strictly after signature verification passes.
        incoming_phone_number_id = extract_phone_number_id(change)
        hospital = db.find_hospital_by_phone_number_id(incoming_phone_number_id)
        if hospital is None:
            logger.warning(
                "Webhook received for unrecognized/inactive phone_number_id=%s — no matching hospital, ignoring",
                incoming_phone_number_id,
            )
            return Response(status_code=200)

        # Each hospital has its own app_secret (SPEC Section 4's app_secret_ref) —
        # verify against *that* hospital's secret, not a single global one. A
        # payload signed with hospital A's secret can never pass for hospital B's
        # phone_number_id, even though both are handled by this one endpoint.
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not validate_webhook_signature(body, signature, hospital.app_secret):
            logger.warning("Invalid webhook signature for hospital_id=%s (phone_number_id=%s)", hospital.id, incoming_phone_number_id)
            raise HTTPException(status_code=403, detail="Invalid signature")

        # Ignore status updates (delivered, read, etc.) — after signature
        # verification, same as everything else, even though there's nothing to
        # act on either way.
        if "statuses" in change:
            return Response(status_code=200)

        message = change["messages"][0]
        phone = message["from"]
        reply = parse_incoming_message(message)
        wa = _get_whatsapp_client(hospital)

        if reply["type"] == "audio":
            # No transcription pipeline (no AI/LLM in this build) — bypass the state
            # machine entirely and tell the patient to use text instead.
            await wa.send_text(phone, "I couldn't process your audio. Could you send it as text instead?")
            return Response(status_code=200)

    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning("Malformed or unexpected webhook payload, ignoring: %s", body[:500])
        return Response(status_code=200)

    # Prevent concurrent processing for the same (hospital, phone) pair
    if not _acquire_message_lock(hospital.id, phone):
        logger.info("Message from %s (hospital %s) skipped (already processing)", phone, hospital.id)
        return Response(status_code=200)

    logger.info("Message lock acquired for %s (hospital %s), type=%s", phone, hospital.id, reply["type"])
    try:
        await _process_message(wa, hospital, phone, reply)
    finally:
        _release_message_lock(hospital.id, phone)

    return Response(status_code=200)


async def _process_message(wa: WhatsAppClient, hospital: db.Hospital, phone: str, reply: dict) -> None:
    """Process a single already-parsed incoming message with the (hospital, phone) lock already held."""
    logger.info("Dispatching message from %s (hospital %s) to booking_flow: %s", phone, hospital.id, reply)
    HISTORY.add(phone, "user", reply.get("text") or reply.get("title") or f"[{reply.get('type')}]")
    await handle_incoming(wa, SESSIONS, phone, hospital.id, reply, hospital.name)
    logger.info("booking_flow.handle_incoming returned for %s", phone)


@app.post("/internal/send-reminders")
async def trigger_reminders(request: Request):
    """Hit by an external cron job (SPEC Section 3.5) — not an in-process scheduler.
    Loops over every active hospital (SPEC Section 12.2), sending each one's
    reminders with its own credentials and its own reminder_offsets_hours."""
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403)

    sent_by_hospital = {}
    for hospital in db.get_active_hospitals():
        wa = _get_whatsapp_client(hospital)
        sent_by_hospital[hospital.name] = await send_reminders(wa, hospital.id, hospital.reminder_offsets_hours)

    return {"sent": sum(sent_by_hospital.values()), "by_hospital": sent_by_hospital}


@app.post("/internal/top-up-slots")
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
