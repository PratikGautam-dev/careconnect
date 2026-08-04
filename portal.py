# portal.py
"""
Section 12.7: a self-serve bookings dashboard for a hospital's OWN staff --
distinct from admin/onboarding.py's platform-admin routes (ADMIN_SECRET,
one shared secret for whoever runs this whole product across every tenant).
This is the other side of that: each hospital logs in with its own password
and sees only ITS OWN appointments (hospital_id-scoped throughout, same
isolation discipline as every other query in db/repository.py).

Only meaningful for Tier 1 hospitals today -- Tier 2/3 connectors don't
implement create_booking() yet (connectors.py), so there are no appointments
rows for a Tier 2/3 hospital to show here regardless; nothing in this module
special-cases that, it just naturally renders an empty list.

Auth: a hospital sets one password (hashed, db.hash_portal_password() /
Section 12.7's portal_password_hash column) during onboarding or via the
edit-tenant form. Login exchanges that password for a signed, httponly
session cookie -- HMAC-SHA256 over "hospital_id.expires_epoch" using
PORTAL_SECRET, stdlib only (no new session/JWT dependency), same
"basic protection, not production-grade auth" posture as ADMIN_SECRET/
INTERNAL_SECRET elsewhere in this project. Not a bearer-token-per-request
scheme like those two, because this page is meant to be *browsed* (a
dashboard you stay logged into), not hit once per admin action.
"""
import hashlib
import hmac
import html
import os
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import db.repository as db
from admin.onboarding import _parse_offsets, _validate_doctor_fields
from admin.theme import STYLE as _STYLE

router = APIRouter()

PORTAL_SECRET = os.environ.get("PORTAL_SECRET", "")
_COOKIE_NAME = "portal_session"
_SESSION_TTL_SECONDS = 24 * 60 * 60  # 24h -- re-login daily, deliberately short given the "basic auth" posture
_WEEKDAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _sign_session(hospital_id: int, expires_at: int) -> str:
    payload = f"{hospital_id}.{expires_at}"
    sig = hmac.new(PORTAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_session(cookie_value: str) -> int | None:
    """Returns the hospital_id the cookie is valid for, or None if missing,
    malformed, tampered with, or expired."""
    if not cookie_value:
        return None
    parts = cookie_value.split(".")
    if len(parts) != 3:
        return None
    hospital_id_str, expires_str, sig = parts
    payload = f"{hospital_id_str}.{expires_str}"
    expected_sig = hmac.new(PORTAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        hospital_id = int(hospital_id_str)
        expires_at = int(expires_str)
    except ValueError:
        return None
    if time.time() > expires_at:
        return None
    return hospital_id


def _current_hospital(request: Request):
    hospital_id = _verify_session(request.cookies.get(_COOKIE_NAME, ""))
    if hospital_id is None:
        return None
    return db.get_hospital(hospital_id)


def _login_html(error: str | None = None) -> str:
    error_html = f'<div class="error-banner">{html.escape(error)}</div>' if error else ""
    return f"""<!doctype html>
<html>
<head><title>Bookings portal login</title>{_STYLE}</head>
<body>
<div class="login-shell">
  <div class="login-card">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">Hospital Onboarding</span>
      <span class="brand-sub">— bookings portal</span>
    </div>
    {error_html}
    <p class="step-desc">Log in with your hospital's bookings portal password to see your WhatsApp appointment bookings.</p>
    <form method="post" action="/portal/login">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" required autofocus>
      <button type="submit" style="margin-top: 18px; width: 100%;">Log in</button>
    </form>
  </div>
</div>
</body>
</html>"""


def _portal_nav(active: str) -> str:
    links = [("bookings", "/portal/bookings", "Bookings"), ("doctors", "/portal/doctors", "Doctors & departments"),
             ("settings", "/portal/settings", "Hospital settings")]
    items = "".join(
        f'<a href="{href}"{" style=\"font-weight:600;color:var(--sage-deep);\"" if key == active else ""}>{label}</a>'
        for key, href, label in links
    )
    return f'<div class="brand-nav">{items}<a href="/portal/logout">Log out</a></div>'


def _bookings_html(hospital, appointments: list) -> str:
    booked = sum(1 for a in appointments if a.status == "booked")
    cancelled = sum(1 for a in appointments if a.status == "cancelled")
    rescheduled = sum(1 for a in appointments if a.status == "rescheduled")

    if appointments:
        rows = "".join(
            f"""<tr>
              <td>{html.escape(a.scheduled_at.strftime('%d %b %Y, %H:%M'))}</td>
              <td>{html.escape(a.phone)}</td>
              <td>{html.escape(a.department_name)}</td>
              <td>{html.escape(a.doctor_name)}</td>
              <td><span class="pill pill-{a.status}">{html.escape(a.status)}</span></td>
            </tr>"""
            for a in appointments
        )
        table = f"""<table>
          <thead><tr><th>Scheduled for</th><th>Patient phone</th><th>Department</th><th>Doctor</th><th>Status</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        table = '<div class="empty-note">No bookings yet — once patients book through WhatsApp, they\'ll show up here.</div>'

    return f"""<!doctype html>
<html>
<head><title>Bookings — {html.escape(hospital.name)}</title>{_STYLE}
<style>
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--sage-line); }}
  th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint); }}
</style>
</head>
<body>
<div class="shell no-rail">
  <div class="brand-row" style="grid-column: 1 / -1;">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">{html.escape(hospital.name)}</span>
      <span class="brand-sub">— bookings portal</span>
    </div>
    {_portal_nav("bookings")}
  </div>
  <main class="main">
    <div class="page-header"><h2>Bookings</h2></div>
    <div class="stat-row">
      <div class="stat-tile"><div class="stat-value">{len(appointments)}</div><div class="stat-label">Total</div></div>
      <div class="stat-tile"><div class="stat-value">{booked}</div><div class="stat-label">Booked</div></div>
      <div class="stat-tile"><div class="stat-value">{cancelled}</div><div class="stat-label">Cancelled</div></div>
      <div class="stat-tile"><div class="stat-value">{rescheduled}</div><div class="stat-label">Rescheduled</div></div>
    </div>
    {table}
  </main>
</div>
</body>
</html>"""


def _settings_html(hospital, errors: list[str] | None = None, values: dict | None = None, saved: bool = False) -> str:
    v = values or {}

    def esc(key: str, default: str = "") -> str:
        return html.escape(str(v.get(key, default)))

    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error-banner"><strong>Please fix the following:</strong><ul>{items}</ul></div>'
    elif saved:
        error_html = '<div class="ok-box">Saved.</div>'

    return f"""<!doctype html>
<html>
<head><title>Settings — {html.escape(hospital.name)}</title>{_STYLE}</head>
<body>
<div class="shell no-rail">
  <div class="brand-row" style="grid-column: 1 / -1;">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">{html.escape(hospital.name)}</span>
      <span class="brand-sub">— bookings portal</span>
    </div>
    {_portal_nav("settings")}
  </div>
  <main class="main">
    {error_html}
    <div class="page-header"><h2>Hospital settings</h2></div>
    <p class="step-desc">
      Credentials (WhatsApp connection, data tier) aren't editable here — contact whoever set up this
      platform for those. This covers the patient-facing details you're likely to actually change yourself.
    </p>
    <form method="post" action="/portal/settings">
      <label for="welcome_message_text">Welcome message text</label>
      <textarea id="welcome_message_text" name="welcome_message_text" rows="2">{esc('welcome_message_text', hospital.welcome_message_text or '')}</textarea>

      <div class="field-row">
        <div>
          <label for="reminder_offsets_hours">Reminder offsets (comma-separated hours)</label>
          <input type="text" id="reminder_offsets_hours" name="reminder_offsets_hours"
                 value="{esc('reminder_offsets_hours', ','.join(str(o) for o in hospital.reminder_offsets_hours))}">
          <p class="field-hint">e.g. 24,1 sends a reminder one day before and one hour before.</p>
        </div>
        <div>
          <label for="reminder_template_name">Reminder template name</label>
          <input type="text" id="reminder_template_name" name="reminder_template_name"
                 value="{esc('reminder_template_name', hospital.reminder_template_name or '')}">
          <p class="field-hint">Must match a message template approved in Meta's WhatsApp Manager.</p>
        </div>
      </div>

      <div class="nav-buttons">
        <span></span>
        <button type="submit">Save changes</button>
      </div>
    </form>
  </main>
</div>
</body>
</html>"""


def _doctor_fields_html(doctor: dict | None = None) -> str:
    """Shared by the add-doctor and edit-doctor forms. working_hours holds at
    most two "HH:MM-HH:MM" ranges (Shift 1 / Shift 2) -- unlike the onboarding
    wizard's dynamically-repeatable shift rows, a fixed two-shift form covers
    the vast majority of real doctor schedules without needing the wizard's
    template-cloning JS machinery for what's a single-doctor-at-a-time page."""
    doctor = doctor or {}
    days = set(doctor.get("working_days") or [])
    hours = doctor.get("working_hours") or []
    shift1 = hours[0].split("-") if len(hours) > 0 else ["", ""]
    shift2 = hours[1].split("-") if len(hours) > 1 else ["", ""]

    days_html = "".join(
        f'<label class="checkbox-row"><input type="checkbox" name="working_days" value="{d}" '
        f'{"checked" if d in days else ""}> {d}</label>'
        for d in _WEEKDAY_ABBREVS
    )

    return f"""
      <div class="field-row">
        <div><label>Name</label><input type="text" name="name" value="{html.escape(doctor.get('name', ''))}" required></div>
        <div><label>Specialization</label><input type="text" name="specialization" value="{html.escape(doctor.get('specialization') or '')}"></div>
      </div>
      <div class="field-row">
        <div><label>Qualification</label><input type="text" name="qualification" value="{html.escape(doctor.get('qualification') or '')}"></div>
        <div><label>Years experience</label><input type="number" min="0" name="years_experience" value="{doctor.get('years_experience') or ''}"></div>
      </div>
      <label>Working days</label>
      {days_html}
      <div class="field-row">
        <div>
          <label>Shift 1</label>
          <div class="shift-row">
            <input type="time" name="shift1_start" value="{html.escape(shift1[0])}">
            <span class="shift-sep">to</span>
            <input type="time" name="shift1_end" value="{html.escape(shift1[1])}">
          </div>
        </div>
        <div>
          <label>Shift 2 (optional)</label>
          <div class="shift-row">
            <input type="time" name="shift2_start" value="{html.escape(shift2[0])}">
            <span class="shift-sep">to</span>
            <input type="time" name="shift2_end" value="{html.escape(shift2[1])}">
          </div>
        </div>
      </div>
      <label>Slot duration (minutes)</label>
      <input type="number" min="1" name="slot_duration_minutes" value="{doctor.get('slot_duration_minutes') or 30}">
      <p class="field-hint">How long each appointment lasts — e.g. 20 means a new bookable slot every 20 minutes.</p>
    """


def _doctors_html(hospital, departments: list[dict], doctors: list[dict], errors: list[str] | None = None) -> str:
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error-banner"><strong>Please fix the following:</strong><ul>{items}</ul></div>'

    dept_options = "".join(f'<option value="{d["id"]}">{html.escape(d["name"])}</option>' for d in departments)

    if doctors:
        rows = "".join(
            f"""<div class="list-row">
              <div class="list-row-main">
                <span class="list-row-title">{html.escape(doc['name'])}</span>
                <span class="list-row-sub">{html.escape(doc['department_name'])}{' · ' + html.escape(doc['specialization']) if doc.get('specialization') else ''}</span>
              </div>
              <div class="list-row-meta">
                <a class="btn-secondary" href="/portal/doctors/{doc['id']}/edit">Edit</a>
              </div>
            </div>"""
            for doc in doctors
        )
        doctors_list = f'<div class="card-list">{rows}</div>'
    else:
        doctors_list = '<div class="empty-note">No doctors added yet.</div>'

    add_department_form = """
    <form method="post" action="/portal/departments" style="margin-top: 12px;">
      <div class="field-row">
        <div><input type="text" name="name" placeholder="New department name" required></div>
        <div><button type="submit" class="small" style="width:auto;">+ Add department</button></div>
      </div>
    </form>"""

    add_doctor_form = f"""
    <form method="post" action="/portal/doctors" style="margin-top: 12px;">
      <label>Department</label>
      <select name="department_id" required>{dept_options}</select>
      {_doctor_fields_html()}
      <div class="nav-buttons">
        <span></span>
        <button type="submit">Add doctor</button>
      </div>
    </form>""" if departments else '<p class="hint">Add a department first before adding a doctor.</p>'

    return f"""<!doctype html>
<html>
<head><title>Doctors &amp; departments — {html.escape(hospital.name)}</title>{_STYLE}
<style>select {{ width: 100%; font-family: var(--font-body); font-size: 14px; padding: 10px 12px; border: 1px solid var(--sage-line); border-radius: 8px; background: var(--paper); color: var(--ink); margin-top: 6px; }}</style>
</head>
<body>
<div class="shell no-rail">
  <div class="brand-row" style="grid-column: 1 / -1;">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">{html.escape(hospital.name)}</span>
      <span class="brand-sub">— bookings portal</span>
    </div>
    {_portal_nav("doctors")}
  </div>
  <main class="main">
    {error_html}
    <div class="page-header"><h2>Doctors &amp; departments</h2></div>
    {doctors_list}

    <h3 style="margin-top: 32px; font-family: var(--font-body); font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint);">Add a department</h3>
    {add_department_form}

    <h3 style="margin-top: 32px; font-family: var(--font-body); font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint);">Add a doctor</h3>
    {add_doctor_form}
  </main>
</div>
</body>
</html>"""


def _doctor_edit_html(hospital, doctor: dict, errors: list[str] | None = None) -> str:
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error-banner"><strong>Please fix the following:</strong><ul>{items}</ul></div>'

    return f"""<!doctype html>
<html>
<head><title>Edit {html.escape(doctor['name'])} — {html.escape(hospital.name)}</title>{_STYLE}</head>
<body>
<div class="shell no-rail">
  <div class="brand-row" style="grid-column: 1 / -1;">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">{html.escape(hospital.name)}</span>
      <span class="brand-sub">— bookings portal</span>
    </div>
    {_portal_nav("doctors")}
  </div>
  <main class="main">
    {error_html}
    <p class="eyebrow">Editing doctor</p>
    <h2>{html.escape(doctor['name'])}</h2>
    <p class="step-desc">Changing the working pattern regenerates this doctor's upcoming bookable slots — already-booked appointments are never affected.</p>
    <form method="post" action="/portal/doctors/{doctor['id']}/edit">
      {_doctor_fields_html(doctor)}
      <div class="nav-buttons">
        <a class="btn-secondary" href="/portal/doctors">Cancel</a>
        <button type="submit">Save changes</button>
      </div>
    </form>
  </main>
</div>
</body>
</html>"""


@router.get("/portal/login", response_class=HTMLResponse)
async def portal_login_form():
    return _login_html()


@router.post("/portal/login", response_class=HTMLResponse)
async def portal_login_submit(password: str = Form("")):
    hospital = db.find_hospital_by_portal_password(password) if password else None
    if hospital is None:
        return HTMLResponse(_login_html("Incorrect password."), status_code=403)

    expires_at = int(time.time()) + _SESSION_TTL_SECONDS
    cookie_value = _sign_session(hospital.id, expires_at)
    response = RedirectResponse(url="/portal/bookings", status_code=303)
    response.set_cookie(
        _COOKIE_NAME, cookie_value, max_age=_SESSION_TTL_SECONDS,
        httponly=True, samesite="lax",
        # Not secure=True: this project also runs over plain http in local
        # dev (Section 6, no reverse-proxy/TLS assumption baked in) -- same
        # "basic protection, not production-grade auth" tradeoff as
        # ADMIN_SECRET/INTERNAL_SECRET being passed in plaintext elsewhere.
    )
    return response


@router.get("/portal/logout")
async def portal_logout():
    response = RedirectResponse(url="/portal/login", status_code=303)
    response.delete_cookie(_COOKIE_NAME)
    return response


@router.get("/portal/bookings", response_class=HTMLResponse)
async def portal_bookings(request: Request):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    appointments = db.get_all_appointments_for_hospital(hospital.id)
    return _bookings_html(hospital, appointments)


@router.get("/portal/settings", response_class=HTMLResponse)
async def portal_settings_form(request: Request):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    return _settings_html(hospital)


@router.post("/portal/settings", response_class=HTMLResponse)
async def portal_settings_submit(
    request: Request,
    welcome_message_text: str = Form(""),
    reminder_offsets_hours: str = Form(""),
    reminder_template_name: str = Form(""),
):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)

    # Credentials/data_tier/portal_password_hash are passed through UNCHANGED --
    # this form deliberately can't touch them (Section 12.7 follow-up scope
    # decision: WhatsApp connection details stay operator-only via
    # /admin/edit-tenant, since a bad edit there could break the hospital's
    # own WhatsApp connection).
    db.update_hospital(
        hospital.id,
        name=hospital.name,
        whatsapp_phone_number_id=hospital.whatsapp_phone_number_id,
        access_token=hospital.access_token,
        app_secret=hospital.app_secret,
        timezone=hospital.timezone,
        welcome_message_text=welcome_message_text.strip() or None,
        reminder_offsets_hours=_parse_offsets(reminder_offsets_hours),
        reminder_template_name=reminder_template_name.strip() or None,
        data_tier=hospital.data_tier,
        external_api_base_url=hospital.external_api_base_url,
        external_api_key=hospital.external_api_key,
        portal_password_hash=hospital.portal_password_hash,
        enabled_features=hospital.enabled_features,
    )
    updated = db.get_hospital(hospital.id)
    return _settings_html(updated, saved=True)


@router.get("/portal/doctors", response_class=HTMLResponse)
async def portal_doctors_list(request: Request):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    departments = db.get_departments(hospital.id)
    doctors = db.get_all_doctors_for_hospital(hospital.id)
    return _doctors_html(hospital, departments, doctors)


@router.post("/portal/departments", response_class=HTMLResponse)
async def portal_add_department(request: Request, name: str = Form("")):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)

    name = name.strip()
    if not name:
        departments = db.get_departments(hospital.id)
        doctors = db.get_all_doctors_for_hospital(hospital.id)
        return HTMLResponse(
            _doctors_html(hospital, departments, doctors, ["Department name is required."]), status_code=400
        )
    db.create_department(hospital.id, name)
    return RedirectResponse(url="/portal/doctors", status_code=303)


def _build_working_hours(shift1_start: str, shift1_end: str, shift2_start: str, shift2_end: str) -> str:
    """Joins whichever shift pairs were filled in on the fixed two-shift form
    into the "HH:MM-HH:MM,HH:MM-HH:MM" string _validate_doctor_fields()
    expects -- native <input type="time"> values are always well-formed
    HH:MM or empty, never something like "10-12:00" (the free-text version
    of this field's most common submission error)."""
    ranges = []
    if shift1_start and shift1_end:
        ranges.append(f"{shift1_start}-{shift1_end}")
    if shift2_start and shift2_end:
        ranges.append(f"{shift2_start}-{shift2_end}")
    return ",".join(ranges)


@router.post("/portal/doctors", response_class=HTMLResponse)
async def portal_add_doctor(
    request: Request,
    department_id: str = Form(""),
    name: str = Form(""),
    specialization: str = Form(""),
    qualification: str = Form(""),
    years_experience: str = Form(""),
    working_days: list[str] = Form(default=[]),
    shift1_start: str = Form(""),
    shift1_end: str = Form(""),
    shift2_start: str = Form(""),
    shift2_end: str = Form(""),
    slot_duration_minutes: str = Form(""),
):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)

    departments = db.get_departments(hospital.id)
    doctors = db.get_all_doctors_for_hospital(hospital.id)

    department = db.find_department(hospital.id, department_id)
    if department is None:
        return HTMLResponse(_doctors_html(hospital, departments, doctors, ["Choose a valid department."]), status_code=400)

    hours_raw = _build_working_hours(shift1_start, shift1_end, shift2_start, shift2_end)
    doctor_data, errors = _validate_doctor_fields(
        0, name, specialization, qualification, years_experience, ",".join(working_days), hours_raw, slot_duration_minutes,
    )
    if errors:
        return HTMLResponse(_doctors_html(hospital, departments, doctors, errors), status_code=400)

    db.create_doctor(
        hospital.id, department_id, doctor_data["name"],
        specialization=doctor_data["specialization"],
        qualification=doctor_data["qualification"],
        years_experience=doctor_data["years_experience"],
        working_days=doctor_data["working_days"],
        working_hours=doctor_data["working_hours"],
        slot_duration_minutes=doctor_data["slot_duration_minutes"],
    )
    return RedirectResponse(url="/portal/doctors", status_code=303)


@router.get("/portal/doctors/{doctor_id}/edit", response_class=HTMLResponse)
async def portal_edit_doctor_form(doctor_id: str, request: Request):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return HTMLResponse("<p>No such doctor.</p>", status_code=404)
    return _doctor_edit_html(hospital, doctor)


@router.post("/portal/doctors/{doctor_id}/edit", response_class=HTMLResponse)
async def portal_edit_doctor_submit(
    doctor_id: str,
    request: Request,
    name: str = Form(""),
    specialization: str = Form(""),
    qualification: str = Form(""),
    years_experience: str = Form(""),
    working_days: list[str] = Form(default=[]),
    shift1_start: str = Form(""),
    shift1_end: str = Form(""),
    shift2_start: str = Form(""),
    shift2_end: str = Form(""),
    slot_duration_minutes: str = Form(""),
):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)

    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return HTMLResponse("<p>No such doctor.</p>", status_code=404)

    hours_raw = _build_working_hours(shift1_start, shift1_end, shift2_start, shift2_end)
    doctor_data, errors = _validate_doctor_fields(
        0, name, specialization, qualification, years_experience, ",".join(working_days), hours_raw, slot_duration_minutes,
    )
    if errors:
        submitted = {
            "id": doctor_id, "name": name, "specialization": specialization, "qualification": qualification,
            "years_experience": years_experience, "working_days": working_days,
            "working_hours": [r for r in hours_raw.split(",") if r],
            "slot_duration_minutes": slot_duration_minutes,
        }
        return HTMLResponse(_doctor_edit_html(hospital, submitted, errors), status_code=400)

    db.update_doctor(
        hospital.id, doctor_id, doctor_data["name"],
        specialization=doctor_data["specialization"],
        qualification=doctor_data["qualification"],
        years_experience=doctor_data["years_experience"],
        working_days=doctor_data["working_days"],
        working_hours=doctor_data["working_hours"],
        slot_duration_minutes=doctor_data["slot_duration_minutes"],
    )
    return RedirectResponse(url="/portal/doctors", status_code=303)
