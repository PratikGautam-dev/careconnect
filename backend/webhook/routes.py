# webhook/routes.py
"""
ARCHITECTURE_PLAN.md Phase 4: the landing page, /health, and the inbound
WhatsApp webhook (GET verification + POST message receipt) -- split out of
the former single core/main.py module. Message *processing* itself (the
WA-client cache, lock, and flows.handle_incoming() dispatch) lives in
webhook/dispatch.py; this file is just the HTTP boundary.
"""
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

import db.repository as db
from admin.theme import STYLE as _STYLE
from connectors import ConnectorNotImplementedError
from core.config import get_settings
from core.translations import t
from core.translations.common import (
    AUDIO_NOT_SUPPORTED,
    SYSTEM_ERROR_NOTIFY,
)
from core.whatsapp import extract_phone_number_id, parse_incoming_message, validate_webhook_signature
from webhook.dispatch import SESSIONS, _acquire_message_lock, _get_whatsapp_client, _process_message, _release_message_lock

logger = logging.getLogger(__name__)

_settings = get_settings()
if _settings.WHATSAPP_VERIFY_TOKEN is None:
    raise RuntimeError("WHATSAPP_VERIFY_TOKEN environment variable is required")
VERIFY_TOKEN = _settings.WHATSAPP_VERIFY_TOKEN

router = APIRouter()


# Section 15 follow-up: this used to serve a full marketing landing page
# (hero, phone mockup, feature list) -- genuinely redundant now that the
# Next.js frontend (frontend/src/app/page.tsx, deployed on Vercel) IS the
# real public-facing site; nobody should be landing on the backend's own
# root URL as an end user. What's left is a minimal internal page with just
# two buttons through to the admin/onboarding.py's own minimal entry
# points -- useful if you only have the backend's URL on hand, nothing more.
@router.get("/", response_class=HTMLResponse)
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


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403)


@router.post("/webhook")
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
        if incoming_phone_number_id is None:
            logger.warning("Webhook payload missing metadata.phone_number_id, ignoring: %s", body[:500])
            return Response(status_code=200)
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

        # CareConnect account/identity layer (db/schema.sql's own comment on
        # care_connect_accounts): `contacts[0].wa_id` is Meta's own stable
        # sender id -- today numerically identical to `phone` (message["from"])
        # on every real payload, but kept as its own value (not just reused
        # from `phone`) so a future identifier that genuinely differs (e.g. a
        # username-first contact) is a payload-shape change, not a code
        # change. `profile.name` is the sender's own WhatsApp DISPLAY name
        # (not a stable @username -- Meta's Cloud API doesn't expose one
        # distinct from phone/wa_id as of this writing), stored as the
        # closest available stand-in until Meta exposes a real username field.
        contact = (change.get("contacts") or [{}])[0]
        provider_user_id = contact.get("wa_id") or phone
        username = (contact.get("profile") or {}).get("name")

        if reply["type"] == "audio":
            # No transcription pipeline (no AI/LLM in this build) — bypass the state
            # machine entirely and tell the patient to use text instead. Outside
            # flows.py's normal dispatch, so language is looked up directly off
            # the session here rather than threaded in as a parameter.
            language = SESSIONS.get(hospital.id, phone).get("language")
            await wa.send_text(phone, t(AUDIO_NOT_SUPPORTED, language))
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
        await _process_message(wa, hospital, phone, reply, provider_user_id=provider_user_id, username=username)
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
            await wa.send_text(phone, t(SYSTEM_ERROR_NOTIFY, language))
        except Exception:
            logger.exception("Also failed to record/notify the handoff for %s (hospital %s)", phone, hospital.id)
    finally:
        _release_message_lock(hospital.id, phone)

    return Response(status_code=200)
