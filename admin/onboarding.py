# admin/onboarding.py
"""
Guided onboarding wizard (SPEC Section 12.1, Phase 10) — a plain server-rendered
form that lets a new hospital be added without touching the database or code
directly. Deliberately no Jinja2/JS framework: "minimal maintenance" per the
project's own priorities, and this is v1 of the guided wizard, not the later
Embedded Signup flow (Section 12.5) — the operator still enters the hospital's
own Meta credentials by hand here (see Section 12.3's constraint that the
hospital's own Meta business/number setup, verification, and System User token
must already exist before this form is used; this form does not create any of
that). The static instructional copy below the page title walks through Meta's
own Steps 1-4 (Section 12.1) so the hospital admin isn't left to go find that
information themselves.

Protected by a shared secret (ADMIN_SECRET env var), same pattern as
core/main.py's INTERNAL_SECRET — basic protection against an unauthenticated
stranger creating hospital rows (and storing real API credentials) on a
deployed instance, not a full auth system.
"""
import html
import os
import re

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse

import db.repository as db
from db.connection import IntegrityError

router = APIRouter()

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")

_WEEKDAY_ABBREVS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
_TIME_RANGE_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
_VALID_TIERS = {"tier1", "tier2", "tier3"}

_DOCTOR_LINE_HINT = (
    "Name | Specialization | Qualification | Years experience | Working days | Working hours | Slot minutes"
)
_DOCTOR_LINE_EXAMPLE = (
    "Dr. Anjali Rao | Cardiologist | MBBS, MD | 12 | Mon,Tue,Wed,Thu,Fri | 10:00-13:00,17:00-20:00 | 20"
)

_PAGE_STYLE = """
<style>
  body { font-family: sans-serif; max-width: 680px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  label { display: block; margin-top: 1rem; font-weight: bold; }
  input[type=text], input[type=password], textarea { width: 100%; padding: 0.4rem; margin-top: 0.25rem; box-sizing: border-box; font-family: inherit; }
  textarea { height: 6rem; font-family: monospace; }
  textarea#departments_text { height: 9rem; }
  button { margin-top: 1.5rem; padding: 0.6rem 1.2rem; font-size: 1rem; }
  .hint { color: #666; font-size: 0.85rem; margin-top: 0.15rem; }
  .error { background: #fdecea; border: 1px solid #f5c2c0; color: #7a1f1a; padding: 0.75rem; border-radius: 4px; }
  .ok { background: #e9f8ee; border: 1px solid #b7e4c7; color: #1e5c34; padding: 0.75rem; border-radius: 4px; }
  .steps { background: #f5f7fa; border: 1px solid #dde3ea; border-radius: 4px; padding: 0.75rem 1rem; }
  .steps ol { margin: 0.5rem 0 0 1.1rem; padding: 0; }
  .steps li { margin-bottom: 0.6rem; }
  .radio-row { font-weight: normal; display: flex; align-items: baseline; gap: 0.4rem; margin-top: 0.5rem; }
  .radio-row input { width: auto; margin: 0; }
  fieldset { border: 1px solid #dde3ea; border-radius: 4px; margin-top: 1rem; padding: 0.75rem 1rem; }
  legend { font-weight: bold; padding: 0 0.3rem; }
</style>
"""

_META_SETUP_STEPS = """
<div class="steps">
  <strong>Before you fill in the credentials below</strong> — Meta requires these
  steps to exist for the hospital's own WhatsApp number. Do these first if they
  aren't done yet:
  <ol>
    <li><strong>Create a Meta Business Account</strong> at
      <a href="https://business.facebook.com" target="_blank" rel="noopener">business.facebook.com</a> —
      sign in and create a Business Account for the hospital.</li>
    <li><strong>Set up WhatsApp on a Meta app</strong> at
      <a href="https://developers.facebook.com" target="_blank" rel="noopener">developers.facebook.com</a> —
      create an app, then add the WhatsApp product to it.</li>
    <li><strong>Business verification + production number + payment method</strong> —
      verify the hospital's real business, register their production WhatsApp number,
      and add a payment method (it's free to add — you're only charged per message later).</li>
    <li><strong>Generate a permanent token</strong> — in Business Settings → Users →
      System Users, generate a <strong>System User access token</strong>. Do not use
      the default temporary token from the API Setup page — it expires roughly every
      24 hours, while a System User token doesn't.</li>
  </ol>
</div>
"""


def _form_html(errors: list[str] | None = None, values: dict | None = None) -> str:
    v = values or {}

    def esc(key: str) -> str:
        return html.escape(str(v.get(key, "")))

    def checked(key: str, option: str, default: str) -> str:
        return "checked" if v.get(key, default) == option else ""

    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error"><strong>Please fix the following:</strong><ul>{items}</ul></div>'

    return f"""<!doctype html>
<html>
<head><title>Onboard a new hospital</title>{_PAGE_STYLE}</head>
<body>
  <h1>Onboard a new hospital</h1>
  {_META_SETUP_STEPS}
  {error_html}
  <form method="post" action="/admin/onboard-hospital">
    <label>Admin secret</label>
    <input type="password" name="admin_secret" value="{esc('admin_secret')}" required>

    <label>Hospital name</label>
    <input type="text" name="name" value="{esc('name')}" required>

    <label>WhatsApp phone_number_id (Step 5)</label>
    <input type="text" name="whatsapp_phone_number_id" value="{esc('whatsapp_phone_number_id')}" required>

    <label>Access token (Step 5 — the System User token from Step 4)</label>
    <input type="text" name="access_token" value="{esc('access_token')}">

    <label>App secret (Step 5)</label>
    <input type="text" name="app_secret" value="{esc('app_secret')}">

    <label>Welcome message text</label>
    <textarea name="welcome_message_text">{esc('welcome_message_text')}</textarea>

    <label>Reminder offsets (comma-separated hours)</label>
    <input type="text" name="reminder_offsets_hours" value="{esc('reminder_offsets_hours') or '24'}" placeholder="24,1">

    <label>Reminder template name</label>
    <input type="text" name="reminder_template_name" value="{esc('reminder_template_name')}">

    <fieldset>
      <legend>Data connection (Step 6)</legend>
      <label class="radio-row"><input type="radio" name="data_tier" value="tier1" {checked('data_tier', 'tier1', 'tier1')}>
        Use this platform to manage my appointments (default — no further setup needed)</label>
      <label class="radio-row"><input type="radio" name="data_tier" value="tier2" {checked('data_tier', 'tier2', 'tier1')}>
        Connect my existing system's API</label>
      <label class="radio-row"><input type="radio" name="data_tier" value="tier3" {checked('data_tier', 'tier3', 'tier1')}>
        Connect my database directly</label>

      <label>API base URL (only if "Connect my existing system's API" above)</label>
      <input type="text" name="api_base_url" value="{esc('api_base_url')}">
      <label>API key (only if "Connect my existing system's API" above)</label>
      <input type="text" name="api_key" value="{esc('api_key')}">
      <p class="hint">
        "Connect my database directly" is not self-serve — it requires a secure/VPN-reachable
        connection and a scoped-down database user, set up as a manually-assisted engagement.
        No fields to fill in here for that option; contact us to arrange it.
      </p>
    </fieldset>

    <label>Departments and doctors (Step 7)</label>
    <div class="hint">
      Start each department with a line beginning with <code>#</code>, then list its doctors,
      one per line, as:<br>
      <code>{html.escape(_DOCTOR_LINE_HINT)}</code><br>
      Specialization, qualification, and years experience may be left blank (still needs the
      surrounding <code>|</code>). Working days: comma-separated Mon-Sun. Working hours:
      comma-separated HH:MM-HH:MM ranges. Slot minutes drives real slot generation (Section 12.1.1).
    </div>
    <textarea id="departments_text" name="departments_text" placeholder="# Cardiology&#10;{html.escape(_DOCTOR_LINE_EXAMPLE)}">{esc('departments_text')}</textarea>

    <button type="submit">Create hospital</button>
  </form>
</body>
</html>"""


def _confirmation_html(hospital, departments: list[dict]) -> str:
    dept_items = "".join(
        f"<li>{html.escape(d['name'])}: "
        f"{html.escape(', '.join(doc['name'] for doc in d['doctors']))}</li>"
        for d in departments
    )
    tier_note = {
        "tier1": "Using this platform's own database to manage appointments (Tier 1).",
        "tier2": "Connected to the hospital's existing API (Tier 2) — the base URL/key were "
                 "stored, but no connector logic runs against them yet.",
        "tier3": "Flagged for direct database connection (Tier 3) — this is a manually-assisted "
                 "engagement, not self-serve; we'll be in touch to arrange secure access.",
    }[hospital.data_tier]
    return f"""<!doctype html>
<html>
<head><title>Hospital onboarded</title>{_PAGE_STYLE}</head>
<body>
  <h1>Hospital created</h1>
  <div class="ok">
    <strong>{html.escape(hospital.name)}</strong> was created with hospital ID
    <strong>{hospital.id}</strong> (phone_number_id: {html.escape(hospital.whatsapp_phone_number_id)}).
  </div>
  <p>{html.escape(tier_note)}</p>
  <h3>Departments</h3>
  <ul>{dept_items}</ul>
  <p class="hint">
    Reminder: this only recorded the credentials you entered — the hospital's own
    Meta Business/WhatsApp number verification and System User access token must
    already have been set up on Meta's side beforehand (Section 12.3). If that
    wasn't done first, outbound messages and webhook signature validation for
    this hospital will fail until it is.
  </p>
  <p><a href="/admin/onboard-hospital">Onboard another hospital</a></p>
</body>
</html>"""


def _parse_doctor_line(line: str, line_no: int) -> tuple[dict | None, list[str]]:
    segments = line.split("|")
    if len(segments) != 7:
        return None, [
            f'Line {line_no} ("{line}") must have exactly 7 "|"-separated fields: {_DOCTOR_LINE_HINT}'
        ]

    name_raw, specialization_raw, qualification_raw, years_raw, days_raw, hours_raw, duration_raw = (
        s.strip() for s in segments
    )
    errors = []

    if not name_raw:
        errors.append(f"Line {line_no}: doctor name is required.")

    years_experience = None
    if years_raw:
        try:
            years_experience = int(years_raw)
        except ValueError:
            errors.append(f'Line {line_no}: years of experience "{years_raw}" is not a whole number.')

    working_days = [d.strip() for d in days_raw.split(",") if d.strip()]
    if not working_days:
        errors.append(f"Line {line_no}: at least one working day is required (e.g. Mon,Wed,Fri).")
    else:
        bad_days = [d for d in working_days if d not in _WEEKDAY_ABBREVS]
        if bad_days:
            errors.append(f'Line {line_no}: invalid working day(s) {bad_days} — use Mon,Tue,Wed,Thu,Fri,Sat,Sun.')

    working_hours = [h.strip() for h in hours_raw.split(",") if h.strip()]
    if not working_hours:
        errors.append(f"Line {line_no}: at least one working hour range is required (e.g. 10:00-13:00).")
    else:
        bad_ranges = [h for h in working_hours if not _TIME_RANGE_RE.match(h)]
        if bad_ranges:
            errors.append(f'Line {line_no}: invalid working hour range(s) {bad_ranges} — use HH:MM-HH:MM.')

    slot_duration_minutes = None
    if not duration_raw:
        errors.append(f"Line {line_no}: slot duration (minutes) is required.")
    else:
        try:
            slot_duration_minutes = int(duration_raw)
            if slot_duration_minutes <= 0:
                raise ValueError
        except ValueError:
            errors.append(f'Line {line_no}: slot duration "{duration_raw}" must be a positive whole number.')

    if errors:
        return None, errors

    return {
        "name": name_raw,
        "specialization": specialization_raw or None,
        "qualification": qualification_raw or None,
        "years_experience": years_experience,
        "working_days": working_days,
        "working_hours": working_hours,
        "slot_duration_minutes": slot_duration_minutes,
    }, []


def _parse_departments(text: str) -> tuple[list[dict], list[str]]:
    """Parses the "# Department" header + pipe-delimited doctor line DSL
    (Section 12.1 Step 7). Returns (departments, errors). A department is only
    included if it has a non-empty name AND at least one valid doctor line."""
    departments: list[dict] = []
    errors: list[str] = []
    current = None

    for i, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            dept_name = line[1:].strip()
            if not dept_name:
                errors.append(f'Line {i}: "#" department header has no name after it.')
                current = None
                continue
            current = {"name": dept_name, "doctors": []}
            departments.append(current)
            continue

        if current is None:
            errors.append(f'Line {i} ("{line}") appears before any "# Department" header.')
            continue

        doctor, line_errors = _parse_doctor_line(line, i)
        errors.extend(line_errors)
        if doctor is not None:
            current["doctors"].append(doctor)

    departments = [d for d in departments if d["doctors"]]
    return departments, errors


def _parse_offsets(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return [24]
    offsets = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            offsets.append(float(part))
        except ValueError:
            continue
    return offsets or [24]


@router.get("/admin/onboard-hospital", response_class=HTMLResponse)
async def onboard_hospital_form():
    return _form_html()


@router.post("/admin/onboard-hospital", response_class=HTMLResponse)
async def onboard_hospital_submit(
    admin_secret: str = Form(""),
    name: str = Form(""),
    whatsapp_phone_number_id: str = Form(""),
    access_token: str = Form(""),
    app_secret: str = Form(""),
    welcome_message_text: str = Form(""),
    reminder_offsets_hours: str = Form(""),
    reminder_template_name: str = Form(""),
    data_tier: str = Form("tier1"),
    api_base_url: str = Form(""),
    api_key: str = Form(""),
    departments_text: str = Form(""),
):
    values = {
        "admin_secret": admin_secret,
        "name": name,
        "whatsapp_phone_number_id": whatsapp_phone_number_id,
        "access_token": access_token,
        "app_secret": app_secret,
        "welcome_message_text": welcome_message_text,
        "reminder_offsets_hours": reminder_offsets_hours,
        "reminder_template_name": reminder_template_name,
        "data_tier": data_tier,
        "api_base_url": api_base_url,
        "api_key": api_key,
        "departments_text": departments_text,
    }

    if admin_secret != ADMIN_SECRET:
        return HTMLResponse(_form_html(["Incorrect admin secret."], values), status_code=403)

    errors = []
    name = name.strip()
    whatsapp_phone_number_id = whatsapp_phone_number_id.strip()
    if not name:
        errors.append("Hospital name is required.")
    if not whatsapp_phone_number_id:
        errors.append("WhatsApp phone_number_id is required.")

    if data_tier not in _VALID_TIERS:
        errors.append(f'Unrecognized data connection tier "{data_tier}".')
    elif data_tier == "tier2" and not (api_base_url.strip() and api_key.strip()):
        errors.append('"Connect my existing system\'s API" requires both an API base URL and an API key.')

    departments, parse_errors = _parse_departments(departments_text)
    errors.extend(parse_errors)
    if not departments:
        errors.append("At least one department with at least one doctor is required.")

    if errors:
        return HTMLResponse(_form_html(errors, values), status_code=400)

    offsets = _parse_offsets(reminder_offsets_hours)
    # Tier 2's fields only mean something for tier2; tier1/tier3 never store them,
    # regardless of stray values left in the form fields.
    stored_api_base_url = api_base_url.strip() or None if data_tier == "tier2" else None
    stored_api_key = api_key.strip() or None if data_tier == "tier2" else None

    try:
        hospital = db.create_hospital(
            name=name,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            access_token=access_token.strip() or None,
            app_secret=app_secret.strip() or None,
            welcome_message_text=welcome_message_text.strip() or None,
            reminder_offsets_hours=offsets,
            reminder_template_name=reminder_template_name.strip() or None,
            data_tier=data_tier,
            external_api_base_url=stored_api_base_url,
            external_api_key=stored_api_key,
        )
    except IntegrityError:
        errors.append(
            f'A hospital with WhatsApp phone_number_id "{whatsapp_phone_number_id}" already exists — '
            "each hospital must have its own phone_number_id for message routing to work correctly."
        )
        return HTMLResponse(_form_html(errors, values), status_code=400)

    created_departments = []
    for dept in departments:
        created_dept = db.create_department(hospital.id, dept["name"])
        created_doctors = [
            db.create_doctor(
                hospital.id, created_dept["id"], doc["name"],
                specialization=doc["specialization"],
                qualification=doc["qualification"],
                years_experience=doc["years_experience"],
                working_days=doc["working_days"],
                working_hours=doc["working_hours"],
                slot_duration_minutes=doc["slot_duration_minutes"],
            )
            for doc in dept["doctors"]
        ]
        created_departments.append({"name": created_dept["name"], "doctors": created_doctors})

    return _confirmation_html(hospital, created_departments)
