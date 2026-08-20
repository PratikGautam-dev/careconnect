import json
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # must run before os.environ[...] reads below, or db.init_db()'s env reads

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

import db.repository as db
from admin.onboarding import router as onboarding_router
from admin.onboarding_api import router as onboarding_api_router
from admin.tenants_api import router as tenants_api_router
from admin.theme import STYLE as _STYLE
from portal_api import router as portal_api_router
from user_auth import AUTH_SECRET, router as user_auth_router
from connectors import ConnectorNotImplementedError, get_connector_for_hospital
import flows
from core.history import get_history, get_session_store
from core.translations import t
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

# Next.js frontend (frontend/) runs on a separate origin/port (localhost:3000
# in dev, a Vercel domain in prod) and calls this API directly from the
# browser, so it needs CORS -- everything else in this app is either a
# same-origin server-rendered page or a webhook Meta calls server-to-server,
# neither of which needed this before. FRONTEND_ORIGIN lets the deployed
# Vercel URL be added without another code change.
_frontend_origins = ["http://localhost:3000"]
if os.environ.get("FRONTEND_ORIGIN"):
    _frontend_origins.append(os.environ["FRONTEND_ORIGIN"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Section 15: only used by user_auth.py's Google OAuth handshake to hold the
# short-lived state/nonce Authlib generates between /auth/google/login and
# /auth/google/callback -- both routes are on THIS backend's own origin
# (see user_auth.py's module docstring), so this cookie is same-origin
# throughout and never faces the cross-origin-cookie problem portal_api.py's
# Bearer-token session already had to work around. Reuses AUTH_SECRET rather
# than adding yet another secret, since it's scoped to the same
# "user identity" concern that secret already covers.
app.add_middleware(SessionMiddleware, secret_key=AUTH_SECRET or "insecure-dev-only-session-secret")

app.include_router(onboarding_router)
app.include_router(onboarding_api_router)
app.include_router(tenants_api_router)
app.include_router(portal_api_router)
app.include_router(user_auth_router)


# Section 15 follow-up: this used to serve a full marketing landing page
# (hero, phone mockup, feature list) -- genuinely redundant now that the
# Next.js frontend (frontend/src/app/page.tsx, deployed on Vercel) IS the
# real public-facing site; nobody should be landing on the backend's own
# root URL as an end user. What's left is a minimal internal page with just
# two buttons through to the admin/onboarding.py's own minimal entry
# points -- useful if you only have the backend's URL on hand, nothing more.
@app.get("/", response_class=HTMLResponse)
async def landing_page():
    return f"""<!doctype html>
<html>
<head><title>CareConnect</title>{_STYLE}</head>
<body>
<div class="ok-page">
  <div class="brand">
    <div class="brand-mark">H</div>
    <span class="brand-name">DAAP CareConnect</span>
  </div>
  <h1>CareConnect backend</h1>
  <p class="hint">This is the API backend. The product itself lives on the deployed frontend.</p>
  <p>
    <a class="btn-secondary" style="background: var(--sage-deep); color: #fff; border: none;" href="/admin/onboard-hospital">Admin</a>
    &nbsp;&middot;&nbsp;
    <a class="btn-secondary" style="background: var(--sage-deep); color: #fff; border: none;" href="/admin/tenants">Super Admin</a>
  </p>
</div>
</body>
</html>"""



@app.get("/health")
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
        # SPEC Section 12.9's phone-validation follow-up: not a real defense
        # against a malicious payload (that's the HMAC signature check above,
        # already passed by this point -- forging `from` requires already
        # having this hospital's app_secret, at which point phone format is
        # the least of the problem) and not something genuine Meta traffic
        # can trigger either (Meta's webhook payloads always populate `from`
        # with the sender's real WhatsApp ID). This exists purely as cheap
        # defense-in-depth against a malformed/unexpected payload shape --
        # same "ignore it, ack Meta with 200" treatment as every other
        # malformed-payload case in this handler, not a hard error.
        if not db.is_valid_phone(phone):
            logger.warning("Webhook message with invalid/unusable phone %r (hospital %s), ignoring", phone, hospital.id)
            return Response(status_code=200)
        reply = parse_incoming_message(message)
        wa = _get_whatsapp_client(hospital)

        if reply["type"] == "audio":
            # No transcription pipeline (no AI/LLM in this build) — bypass the state
            # machine entirely and tell the patient to use text instead. Outside
            # flows.py's normal dispatch, so language is looked up directly off
            # the session here rather than threaded in as a parameter.
            language = SESSIONS.get(hospital.id, phone).get("language")
            await wa.send_text(phone, t("audio_not_supported", language))
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
    except ConnectorNotImplementedError:
        # SPEC Section 12.6.2: this hospital is configured for a tier with no
        # real connector yet -- a real, loud problem, but not one that should
        # ever crash the webhook itself (same "always ack Meta with 200"
        # pattern as every other failure mode in this handler).
        logger.error("Hospital %s has no working connector for data_tier -- message from %s dropped", hospital.id, phone)
    except Exception:
        # Any OTHER unexpected failure while processing this message (a real
        # bug, not a known/handled case) -- previously propagated uncaught
        # with no patient-facing reply and no record anywhere of what
        # happened. Now: log it loudly, queue it in the human-handoff table
        # (Section 14.5 follow-up) so staff see it in the portal, and tell
        # the patient a person's been notified instead of leaving them with
        # silence. The queue-and-reply half is wrapped in its own try/except
        # -- it must never itself raise past this handler (that would defeat
        # the "always ack Meta with 200" pattern the ConnectorNotImplementedError
        # branch above already relies on), a DB or send failure here just
        # gets logged, not re-raised.
        logger.exception("Unexpected error processing message from %s (hospital %s)", phone, hospital.id)
        try:
            db.create_handoff_request(
                hospital.id, phone, reason="system_error",
                message_text=f"Bot error while handling: {reply.get('text') or reply.get('title') or reply.get('type')}",
            )
            # Outside flows.py's normal dispatch (the failure may have happened
            # inside it), so language is looked up directly off the session --
            # wrapped in the same try/except as everything else here, so a
            # session-store hiccup on top of the original failure still can't
            # escape this handler.
            language = SESSIONS.get(hospital.id, phone).get("language")
            await wa.send_text(phone, t("system_error_notify", language))
        except Exception:
            logger.exception("Also failed to record/notify the handoff for %s (hospital %s)", phone, hospital.id)
    finally:
        _release_message_lock(hospital.id, phone)

    return Response(status_code=200)


async def _process_message(wa: WhatsAppClient, hospital: db.Hospital, phone: str, reply: dict) -> None:
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
    )
    logger.info("Flow router returned for %s (hospital %s)", phone, hospital.id)


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
