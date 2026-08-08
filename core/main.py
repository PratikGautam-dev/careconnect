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

import db.repository as db
from admin.onboarding import router as onboarding_router
from admin.onboarding_api import router as onboarding_api_router
from admin.tenants_api import router as tenants_api_router
from admin.theme import STYLE as _STYLE
from portal import router as portal_router
from portal_api import router as portal_api_router
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

app.include_router(onboarding_router)
app.include_router(onboarding_api_router)
app.include_router(tenants_api_router)
app.include_router(portal_router)
app.include_router(portal_api_router)


# /admin/onboard-hospital IS the client-facing signup flow (gated by
# ADMIN_SECRET only at the final submit step -- "basic protection" against a
# random stranger creating fake hospital rows, not a wall meant to keep real
# prospective hospitals out), so it belongs on the homepage as the main CTA.
# /admin/tenants (every hospital on the whole platform) is different -- that
# one stays off this page; a client has no reason to see or reach it.
#
# Design reference: design-reference/ "DAAP CareConnect" landing mockup
# (WhatsApp Image 2026-08-03 at 01.59.58.jpeg) -- reuses admin/theme.py's
# shared tokens for consistency with the rest of the admin/onboarding/portal
# surface, plus page-specific hero/phone-mockup CSS below that nothing else
# needs. The phone mockup is hand-built HTML/CSS (no image asset), including
# the exact main-menu copy shown in the reference. "Request a product demo"
# has no backend flow to link to yet -- points at a placeholder mailto;
# swap in a real address (or a real demo-request flow) once one exists.
_LANDING_HTML = f"""<!doctype html>
<html>
<head>
<title>DAAP CareConnect — WhatsApp Appointment Booking &amp; Reminder Platform for Hospitals</title>
{_STYLE}
<style>
  /* Section 15.x layout pass (spacing/alignment only -- colors, fonts,
     copy, icons, and branding are unchanged from the values above/below).
     All spacing uses the 8px scale (8/16/24/32/40/48/56/64/80/96) except
     where a specific value was explicitly requested (20px, 36px). */
  .hero-wrap {{ max-width: 1440px; margin: 0 auto; padding: 80px 64px; }}
  .hero-grid {{ display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 80px; align-items: center; }}

  .hero-logo {{ display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }}
  .hero-logo-mark {{
    width: 52px; height: 52px; border-radius: 14px; background: var(--sage-deep);
    color: #fff; display: flex; align-items: center; justify-content: center;
    font-family: var(--font-display); font-weight: 800; font-size: 26px; flex-shrink: 0;
  }}
  .hero-logo-super {{ display: block; font-size: 12px; font-weight: 700; letter-spacing: 0.12em; color: var(--ink-faint); }}
  .hero-logo-word {{ font-family: var(--font-display); font-weight: 800; font-size: 34px; line-height: 1.1; }}
  .hero-logo-word .accent {{ color: var(--sage-deep); }}

  .hero-tagline {{ color: var(--ink-muted); font-size: 14.5px; margin: 0 0 20px; }}

  .hero-heading {{
    font-family: var(--font-display); font-weight: 800; font-size: 40px;
    max-width: 650px; line-height: 1.08; letter-spacing: -0.03em; text-wrap: balance;
    margin: 0 0 32px;
  }}
  .hero-heading .accent {{ color: var(--sage-deep); }}

  .hero-desc {{ color: var(--ink-muted); font-size: 18px; line-height: 1.7; max-width: 620px; margin: 0 0 36px; }}

  .hero-features {{ display: flex; flex-wrap: wrap; gap: 32px; margin-bottom: 40px; }}
  .hero-feature {{ display: flex; align-items: flex-start; gap: 16px; padding: 8px 0; flex: 1 1 160px; }}
  .hero-feature-icon {{
    width: 40px; height: 40px; border-radius: 10px; background: var(--success-tint); color: var(--success);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }}
  .hero-feature strong {{ display: block; font-size: 15px; color: var(--ink); }}
  .hero-feature span {{ display: block; font-size: 13px; color: var(--ink-muted); margin-top: 4px; }}

  .hero-ctas {{ display: flex; gap: 16px; flex-wrap: wrap; align-items: center; margin-bottom: 20px; }}
  .hero-ctas a {{
    height: 56px; padding: 0 32px; border-radius: 14px; font-size: 16px; font-weight: 600;
    display: inline-flex; align-items: center; justify-content: center; text-decoration: none;
  }}

  .hero-portal-link {{ display: inline-flex; align-items: center; gap: 4px; color: var(--sage-deep); font-weight: 600; font-size: 14px; text-decoration: none; }}
  .hero-portal-link:hover {{ text-decoration: underline; }}

  /* Phone mockup -- hand-built HTML/CSS, no image asset. */
  .hero-phone-wrap {{ display: flex; justify-content: center; align-items: center; }}
  .phone-frame {{
    width: 312px; border-radius: 32px; background: #0E0E10; padding: 10px;
    box-shadow: 0 24px 60px -20px rgba(20, 40, 32, 0.35);
  }}
  .phone-screen {{ background: #EDE6DA; border-radius: 24px; overflow: hidden; display: flex; flex-direction: column; height: 580px; }}
  .phone-header {{
    background: var(--sage-deep); color: #fff; padding: 12px 14px; display: flex; align-items: center; gap: 10px;
  }}
  .phone-avatar {{
    width: 30px; height: 30px; border-radius: 50%; background: #fff; color: var(--sage-deep);
    display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px; flex-shrink: 0;
  }}
  .phone-header-text {{ line-height: 1.25; }}
  .phone-header-text strong {{ display: block; font-size: 13.5px; }}
  .phone-header-text span {{ display: block; font-size: 10.5px; color: #D9E9E1; letter-spacing: 0.03em; text-transform: uppercase; }}
  .phone-body {{ flex: 1; padding: 16px 14px; overflow: hidden; }}
  .phone-bubble {{
    background: #fff; border-radius: 10px; padding: 12px 14px; font-size: 12.5px; color: var(--ink);
    line-height: 1.55; box-shadow: 0 1px 1px rgba(0,0,0,0.06); max-width: 92%;
  }}
  .phone-bubble ol {{ margin: 6px 0 0; padding-left: 18px; }}
  .phone-bubble li {{ margin-bottom: 2px; }}
  .phone-timestamp {{ display: block; text-align: right; font-size: 10px; color: var(--ink-faint); margin-top: 6px; }}
  .phone-input-bar {{
    background: #F7F5F0; border-top: 1px solid var(--sage-line); padding: 10px 14px;
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
  }}
  .phone-input-bar span:first-child {{ color: var(--ink-faint); font-size: 12.5px; }}
  .phone-mic {{
    width: 28px; height: 28px; border-radius: 50%; background: var(--sage-deep); color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: 12px; flex-shrink: 0;
  }}

  /* Tablet: still two columns, tighter gap and side padding. */
  @media (max-width: 1024px) {{
    .hero-wrap {{ padding: 64px 40px; }}
    .hero-grid {{ gap: 48px; }}
  }}

  /* Mobile: single column. hero-phone-wrap has no `order` override, so it
     stays in its natural DOM position -- last, after the staff portal link. */
  @media (max-width: 640px) {{
    .hero-wrap {{ padding: 48px 24px; }}
    .hero-grid {{ grid-template-columns: 1fr; gap: 48px; }}
    .hero-heading {{ font-size: 32px; }}
    .hero-ctas {{ flex-direction: column; align-items: stretch; }}
    .hero-ctas a {{ width: 100%; }}
  }}
</style>
</head>
<body>
<div class="hero-wrap">
  <div class="hero-grid">
    <div class="hero-content">
      <div class="hero-logo">
        <div class="hero-logo-mark">H</div>
        <div>
          <span class="hero-logo-super">DAAP</span>
          <span class="hero-logo-word">Care<span class="accent">Connect</span></span>
        </div>
      </div>
      <p class="hero-tagline">WhatsApp Appointment Booking &amp; Reminder Platform for Hospitals</p>

      <h1 class="hero-heading">Appointments on <span class="accent">WhatsApp</span>.<br>Managed from one hospital dashboard.</h1>
      <p class="hero-desc">
        Let patients book, reschedule and cancel appointments through WhatsApp. Use this platform's own
        booking database, connect your existing hospital system, or activate directly inside your hospital ERP.
      </p>

      <div class="hero-features">
        <div class="hero-feature">
          <div class="hero-feature-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/><path d="M8 12l2.5 2.5L16 9"/></svg>
          </div>
          <div><strong>No app for patients</strong><span>Works directly on WhatsApp</span></div>
        </div>
        <div class="hero-feature">
          <div class="hero-feature-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 10h8M8 14h5"/></svg>
          </div>
          <div><strong>Simple &amp; guided</strong><span>Menu-driven booking that just works</span></div>
        </div>
        <div class="hero-feature">
          <div class="hero-feature-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 15s1 1.5 2.5 1.5 2.5-.8 2.5-2-1-1.5-2.5-2-2.5-.8-2.5-2 1-2 2.5-2 2.5 1.5 2.5 1.5"/></svg>
          </div>
          <div><strong>Transparent pricing</strong><span>Meta messaging charges may apply</span></div>
        </div>
      </div>

      <div class="hero-ctas">
        <a class="btn-secondary" style="background: var(--sage-deep); color: #fff; border: none;" href="/admin/onboard-hospital">Set up your hospital</a>
        <a class="btn-secondary" href="mailto:hello@example.com?subject=DAAP%20CareConnect%20demo%20request">Request a product demo</a>
      </div>
      <a class="hero-portal-link" href="/portal/login">Open staff booking portal →</a>
    </div>

    <div class="hero-phone-wrap">
      <div class="phone-frame">
        <div class="phone-screen">
          <div class="phone-header">
            <div class="phone-avatar">H</div>
            <div class="phone-header-text">
              <strong>ABC Hospital</strong>
              <span>Business Account</span>
            </div>
          </div>
          <div class="phone-body">
            <div class="phone-bubble">
              Hi! Welcome to ABC Hospital.<br>How can we help you today?<br>Please choose an option below.
              <ol>
                <li>Book an appointment</li>
                <li>Reschedule appointment</li>
                <li>Cancel appointment</li>
                <li>My appointments</li>
                <li>Hospital information</li>
                <li>Talk to reception</li>
              </ol>
              <span class="phone-timestamp">10:30 AM</span>
            </div>
          </div>
          <div class="phone-input-bar">
            <span>Type a message</span>
            <div class="phone-mic">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 15a3 3 0 003-3V6a3 3 0 10-6 0v6a3 3 0 003 3z"/><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M19 11a7 7 0 01-14 0M12 18v3"/></svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def landing_page():
    return _LANDING_HTML


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
