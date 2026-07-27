import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from config.loader import load_config
from core.booking_flow import handle_incoming
from core.history import get_history, get_session_store
from core.whatsapp import WhatsAppClient, parse_incoming_message, validate_webhook_signature
from modules.booking.calendar import CalendarClient
from reminders.scheduler import send_reminders

logger = logging.getLogger(__name__)

CONFIG = load_config()
HISTORY = get_history()
SESSIONS = get_session_store()
HOSPITAL_NAME = CONFIG.get("client", {}).get("name", "the hospital")

WA = WhatsAppClient(
    phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
    access_token=os.environ["WHATSAPP_ACCESS_TOKEN"],
)
APP_SECRET = os.environ["WHATSAPP_APP_SECRET"]
VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")

_calendar_client: CalendarClient | None = None
_redis = None

# In-memory fallback for the per-phone message-processing lock (used when Redis is not available)
_message_locks: dict[str, float] = {}  # phone -> lock expiry timestamp


def _get_redis():
    global _redis
    if _redis is None:
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            import redis
            _redis = redis.from_url(redis_url, decode_responses=True)
    return _redis


def _acquire_message_lock(phone: str, ttl: int = 15) -> bool:
    """Try to acquire a processing lock for this phone. Returns True if acquired."""
    r = _get_redis()
    if r:
        key = f"msg_lock:{phone}"
        return bool(r.set(key, "1", nx=True, ex=ttl))
    # In-memory fallback
    now = time.time()
    expiry = _message_locks.get(phone, 0)
    if now < expiry:
        return False  # Lock still held
    _message_locks[phone] = now + ttl
    return True


def _release_message_lock(phone: str):
    r = _get_redis()
    if r:
        r.delete(f"msg_lock:{phone}")
    else:
        _message_locks.pop(phone, None)


def _get_calendar_client() -> CalendarClient | None:
    """Used only by the reminder job below — the menu booking flow (core/booking_flow.py)
    reads from mock_data.py, not this, until Phase 3 wires it to the real ERP."""
    if not CONFIG.get("modules", {}).get("booking"):
        return None
    global _calendar_client
    if _calendar_client is None:
        booking_cfg = CONFIG["booking"]
        _calendar_client = CalendarClient(
            calendar_id=booking_cfg["calendar_id"],
            calendar_owner_email=booking_cfg["calendar_owner_email"],
            business_hours=booking_cfg["business_hours"],
            timezone=CONFIG["client"].get("timezone", "America/Argentina/Buenos_Aires"),
        )
    return _calendar_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


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
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not validate_webhook_signature(body, signature, APP_SECRET):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()

    try:
        entry = data["entry"][0]
        change = entry["changes"][0]["value"]

        # Ignore status updates (delivered, read, etc.)
        if "statuses" in change:
            return Response(status_code=200)

        message = change["messages"][0]
        phone = message["from"]
        reply = parse_incoming_message(message)

        if reply["type"] == "audio":
            # No transcription pipeline (no AI/LLM in this build) — bypass the state
            # machine entirely and tell the patient to use text instead.
            await WA.send_text(phone, "I couldn't process your audio. Could you send it as text instead?")
            return Response(status_code=200)

    except (KeyError, IndexError):
        return Response(status_code=200)

    # Prevent concurrent processing for the same phone number
    if not _acquire_message_lock(phone):
        logger.info("Message from %s skipped (already processing)", phone)
        return Response(status_code=200)

    try:
        await _process_message(phone, reply)
    finally:
        _release_message_lock(phone)

    return Response(status_code=200)


async def _process_message(phone: str, reply: dict) -> None:
    """Process a single already-parsed incoming message with the phone lock already held."""
    HISTORY.add(phone, "user", reply.get("text") or reply.get("title") or f"[{reply.get('type')}]")
    await handle_incoming(WA, SESSIONS, phone, reply, HOSPITAL_NAME)


@app.post("/internal/send-reminders")
async def trigger_reminders(request: Request):
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403)

    cal = _get_calendar_client()
    if cal is None:
        return {"sent": 0, "error": "booking module disabled"}

    sent = await send_reminders(CONFIG, cal._service, WA)
    return {"sent": sent}
