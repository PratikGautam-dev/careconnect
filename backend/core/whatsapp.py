import hashlib
import hmac
import logging
import httpx
from core.phone import normalize_phone

logger = logging.getLogger(__name__)

WA_API_VERSION = "v22.0"
WA_API_BASE = f"https://graph.facebook.com/{WA_API_VERSION}"


def validate_webhook_signature(body: bytes, signature: str, app_secret: str | None) -> bool:
    """Validate Meta webhook HMAC-SHA256 signature. app_secret is per-hospital
    (SPEC Section 12.2/Phase 9) and can be None for a hospital that hasn't had
    one configured yet (e.g. mid-onboarding) — fail closed rather than raising,
    since hmac.new(None...) would otherwise crash the webhook handler."""
    if not app_secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class WhatsAppClient:
    def __init__(self, phone_number_id: str, access_token: str):
        self._phone_number_id = phone_number_id
        self._token = access_token
        self._client = httpx.AsyncClient(timeout=30)

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def send_text(self, to: str, text: str) -> None:
        to = normalize_phone(to)
        url = f"{WA_API_BASE}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        logger.info("WhatsApp send_text: POSTing to %s for %s", url, to)
        try:
            resp = await self._client.post(url, json=payload, headers=self._headers)
        except httpx.HTTPError:
            logger.exception("WhatsApp send_text request to %s failed (network/transport error)", url)
            return
        if resp.is_success:
            logger.info("WhatsApp send_text: %s OK for %s", resp.status_code, to)
        else:
            logger.error("WhatsApp send_text error %s: %s", resp.status_code, resp.text)

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        url = f"{WA_API_BASE}/{media_id}"
        resp = await self._client.get(url, headers=self._headers)
        resp.raise_for_status()
        data = resp.json()
        download_url = data["url"]
        mime_type = data.get("mime_type", "audio/ogg")
        media_resp = await self._client.get(download_url, headers=self._headers)
        media_resp.raise_for_status()
        return media_resp.content, mime_type

    async def send_list(
        self,
        to: str,
        body_text: str,
        button_text: str,
        sections: list[dict],
        header_text: str | None = None,
        footer_text: str | None = None,
    ) -> None:
        """
        Send a WhatsApp interactive list message (for >3 options).
        sections: [{"title": str, "rows": [{"id": str, "title": str, "description": str?}]}]
        Meta limits: max 10 rows total across all sections, row title <=24 chars,
        row description <=72 chars, button_text <=20 chars.
        """
        to = normalize_phone(to)
        url = f"{WA_API_BASE}/{self._phone_number_id}/messages"
        interactive = {
            "type": "list",
            "body": {"text": body_text},
            "action": {"button": button_text, "sections": sections},
        }
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        logger.info("WhatsApp send_list: POSTing to %s for %s", url, to)
        try:
            resp = await self._client.post(url, json=payload, headers=self._headers)
        except httpx.HTTPError:
            logger.exception("WhatsApp send_list request to %s failed (network/transport error)", url)
            return
        if resp.is_success:
            logger.info("WhatsApp send_list: %s OK for %s", resp.status_code, to)
        else:
            logger.error("WhatsApp send_list error %s: %s", resp.status_code, resp.text)

    async def send_buttons(
        self,
        to: str,
        body_text: str,
        buttons: list[dict],
        header_text: str | None = None,
        footer_text: str | None = None,
    ) -> None:
        """
        Send a WhatsApp interactive reply-button message (max 3 buttons).
        buttons: [{"id": str, "title": str}], title <=20 chars.
        """
        to = normalize_phone(to)
        url = f"{WA_API_BASE}/{self._phone_number_id}/messages"
        interactive = {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons
                ]
            },
        }
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        logger.info("WhatsApp send_buttons: POSTing to %s for %s", url, to)
        try:
            resp = await self._client.post(url, json=payload, headers=self._headers)
        except httpx.HTTPError:
            logger.exception("WhatsApp send_buttons request to %s failed (network/transport error)", url)
            return
        if resp.is_success:
            logger.info("WhatsApp send_buttons: %s OK for %s", resp.status_code, to)
        else:
            logger.error("WhatsApp send_buttons error %s: %s", resp.status_code, resp.text)

    async def send_document(self, to: str, document_url: str, filename: str, caption: str | None = None) -> bool:
        """Section 12.10: the portal's "Send to WhatsApp" action on a patient
        document. `document_url` must be a URL Meta's servers can fetch
        (an S3/R2 presigned URL in production; core/storage.py's
        LocalFileStorage signed URLs are relative/localhost-only and can't
        actually be fetched by Meta -- fine for local dev/testing the rest of
        this feature, a real limitation only once this needs to send for
        real, same as every other "swap for real infra before production"
        note elsewhere in this codebase).

        Unlike send_text/send_list/send_buttons above, this returns a bool
        rather than always None -- the portal needs to show staff a real
        "failed to send" error for this one (uploading a document and
        silently failing to deliver it is a worse outcome than a patient
        never getting a menu prompt), so swallowing the result the same way
        those do isn't the right call here specifically.
        """
        to = normalize_phone(to)
        url = f"{WA_API_BASE}/{self._phone_number_id}/messages"
        document: dict = {"link": document_url, "filename": filename}
        if caption:
            document["caption"] = caption
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": document,
        }
        logger.info("WhatsApp send_document: POSTing to %s for %s", url, to)
        try:
            resp = await self._client.post(url, json=payload, headers=self._headers)
        except httpx.HTTPError:
            logger.exception("WhatsApp send_document request to %s failed (network/transport error)", url)
            return False
        if resp.is_success:
            logger.info("WhatsApp send_document: %s OK for %s", resp.status_code, to)
            return True
        logger.error("WhatsApp send_document error %s: %s", resp.status_code, resp.text)
        return False


def parse_incoming_message(message: dict) -> dict:
    """
    Normalize a raw Meta webhook message object into one of:
      {"type": "text", "text": str}
      {"type": "interactive_reply", "id": str, "title": str}  — a tapped list/button option
      {"type": "audio"}
      {"type": "unsupported"}
    Centralizes payload parsing so nothing else in the app touches Meta's raw shapes.
    """
    msg_type = message.get("type")

    if msg_type == "text":
        return {"type": "text", "text": message.get("text", {}).get("body", "")}

    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        itype = interactive.get("type")
        if itype == "list_reply":
            reply = interactive.get("list_reply", {})
            return {"type": "interactive_reply", "id": reply.get("id", ""), "title": reply.get("title", "")}
        if itype == "button_reply":
            reply = interactive.get("button_reply", {})
            return {"type": "interactive_reply", "id": reply.get("id", ""), "title": reply.get("title", "")}
        return {"type": "unsupported"}

    if msg_type == "audio":
        return {"type": "audio"}

    return {"type": "unsupported"}


def extract_phone_number_id(change: dict) -> str | None:
    """
    The `value.metadata.phone_number_id` field in a Meta webhook payload identifies
    *which* WhatsApp number received the message — i.e. which hospital it's for
    (SPEC Section 12.2 multi-tenant routing). Not to be confused with `message["from"]`,
    which is the sending *patient's* number. Centralized here for the same reason
    as parse_incoming_message: nothing else in the app should touch Meta's raw shape.
    """
    return change.get("metadata", {}).get("phone_number_id")
