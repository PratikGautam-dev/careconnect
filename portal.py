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
from admin.theme import STYLE as _STYLE

router = APIRouter()

PORTAL_SECRET = os.environ.get("PORTAL_SECRET", "")
_COOKIE_NAME = "portal_session"
_SESSION_TTL_SECONDS = 24 * 60 * 60  # 24h -- re-login daily, deliberately short given the "basic auth" posture


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
    <div class="brand-nav">
      <a href="/portal/logout">Log out</a>
    </div>
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
