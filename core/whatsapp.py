import hashlib
import hmac
import logging
import httpx
from core.phone import normalize_phone

logger = logging.getLogger(__name__)

WA_API_VERSION = "v22.0"
WA_API_BASE = f"https://graph.facebook.com/{WA_API_VERSION}"


def validate_webhook_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """Validate Meta webhook HMAC-SHA256 signature."""
    if not signature.startswith("sha256="):
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
        resp = await self._client.post(url, json=payload, headers=self._headers)
        if not resp.is_success:
            logger.error("WhatsApp send error %s: %s", resp.status_code, resp.text)

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
        resp = await self._client.post(url, json=payload, headers=self._headers)
        if not resp.is_success:
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
        resp = await self._client.post(url, json=payload, headers=self._headers)
        if not resp.is_success:
            logger.error("WhatsApp send_buttons error %s: %s", resp.status_code, resp.text)


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
