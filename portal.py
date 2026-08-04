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
import json
import os
import time
from datetime import date as _date
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import connectors
import db.repository as db
from admin.onboarding import _parse_offsets, _validate_doctor_fields
from admin.theme import STYLE as _STYLE
from db.connection import IntegrityError

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


_PORTAL_NAV_LINKS = [
    ("dashboard", "/portal/dashboard", "Dashboard"),
    ("new-booking", "/portal/new-booking", "+ New Booking"),
    ("bookings", "/portal/bookings", "Bookings"),
    ("doctors", "/portal/doctors", "Doctors & departments"),
    ("settings", "/portal/settings", "Hospital settings"),
]


def _portal_nav(active: str) -> str:
    """The horizontal nav strip used by every portal.py page EXCEPT the
    dashboard (Section 12.8), which gets its own vertical sidebar
    (_dashboard_sidebar_html() below) matching the reference design more
    closely -- rebuilding every existing page around a permanent sidebar was
    out of scope for that task, so this keeps working exactly as before,
    just with a "Dashboard" link added so it's reachable from anywhere."""
    items = "".join(
        f'<a href="{href}"{" style=\"font-weight:600;color:var(--sage-deep);\"" if key == active else ""}>{label}</a>'
        for key, href, label in _PORTAL_NAV_LINKS
    )
    return f'<div class="brand-nav">{items}<a href="/portal/logout">Log out</a></div>'


def _dashboard_sidebar_html(hospital, active: str) -> str:
    items = "".join(
        f'<a href="{href}" class="{"active" if key == active else ""}">{label}</a>'
        for key, href, label in _PORTAL_NAV_LINKS
    )
    return f"""
    <div class="dashboard-sidebar">
      <div class="brand">
        <div class="brand-mark">H</div>
        <span class="brand-name">{html.escape(hospital.name)}</span>
      </div>
      {items}
      <a href="/portal/logout" class="logout">Log out</a>
    </div>
    """


_CHART_COLORS = ["#1B4D3E", "#9C7A3D", "#1E9E5A", "#D14343", "#667066", "#5B8A9C", "#B08968"]


def _stat_delta_html(pct: float | None) -> str:
    """pct is None when there's no baseline (zero appointments on the same
    weekday last week) -- shown as "—" rather than a misleading 0%/divide-by-
    zero (db.get_dashboard_stats()'s own docstring explains the choice)."""
    if pct is None:
        return '<span class="stat-delta flat">— vs last week</span>'
    if pct > 0:
        return f'<span class="stat-delta up">&#9650; {pct:g}% vs last week</span>'
    if pct < 0:
        return f'<span class="stat-delta down">&#9660; {abs(pct):g}% vs last week</span>'
    return '<span class="stat-delta flat">No change vs last week</span>'


def _dashboard_html(
    hospital, stats: dict, weekly_counts: list[dict], dept_breakdown: list[dict],
    recent_appointments: list, activity_feed: list[dict],
) -> str:
    stat_tiles = f"""
    <div class="stat-row">
      <div class="stat-tile">
        <div class="stat-value">{stats['today_appointments']}</div>
        <div class="stat-label">Today's Appointments</div>
        {_stat_delta_html(stats['today_appointments_delta_pct'])}
      </div>
      <div class="stat-tile">
        <div class="stat-value">{stats['confirmed_today']}</div>
        <div class="stat-label">Confirmed Today</div>
        {_stat_delta_html(stats['confirmed_today_delta_pct'])}
      </div>
      <div class="stat-tile">
        <div class="stat-value">{stats['new_patients_today']}</div>
        <div class="stat-label">New Patients Today</div>
        {_stat_delta_html(stats['new_patients_today_delta_pct'])}
      </div>
      <div class="stat-tile">
        <div class="stat-value">{stats['no_shows_today']}</div>
        <div class="stat-label">No-Shows Today</div>
        {_stat_delta_html(stats['no_shows_today_delta_pct'])}
      </div>
    </div>
    """

    # Chart.js needs SOME data to draw an axis -- an all-zero week still
    # renders a flat line at 0 correctly, but zero DEPARTMENTS (nothing
    # booked in the last 30 days) has nothing to slice a donut out of, so
    # that one gets an empty-state message instead of an empty canvas.
    weekly_labels = json.dumps([w["label"] for w in weekly_counts])
    weekly_values = json.dumps([w["count"] for w in weekly_counts])

    if dept_breakdown:
        dept_labels = json.dumps([d["department_name"] for d in dept_breakdown])
        dept_values = json.dumps([d["count"] for d in dept_breakdown])
        dept_colors = json.dumps([_CHART_COLORS[i % len(_CHART_COLORS)] for i in range(len(dept_breakdown))])
        legend_rows = "".join(
            f'<div class="chart-legend-row"><span class="chart-legend-swatch" '
            f'style="background:{_CHART_COLORS[i % len(_CHART_COLORS)]}"></span>'
            f'{html.escape(d["department_name"])} ({d["count"]})</div>'
            for i, d in enumerate(dept_breakdown)
        )
        dept_chart_html = f"""
          <canvas id="dept-chart" height="200"></canvas>
          <div class="chart-legend">{legend_rows}</div>
        """
    else:
        dept_labels = dept_values = dept_colors = "[]"
        dept_chart_html = '<div class="empty-note">No appointments in the last 30 days.</div>'

    charts = f"""
    <div class="chart-row">
      <div class="chart-card">
        <h3>Weekly Appointments Trend</h3>
        <canvas id="weekly-chart" height="110"></canvas>
      </div>
      <div class="chart-card">
        <h3>Appointments by Department (30 days)</h3>
        {dept_chart_html}
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <script>
      new Chart(document.getElementById("weekly-chart"), {{
        type: "line",
        data: {{
          labels: {weekly_labels},
          datasets: [{{
            data: {weekly_values}, borderColor: "#1B4D3E", backgroundColor: "rgba(27,77,62,0.08)",
            tension: 0.3, fill: true, pointRadius: 3, pointBackgroundColor: "#1B4D3E",
          }}],
        }},
        options: {{
          plugins: {{ legend: {{ display: false }} }},
          scales: {{ y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }} }},
        }},
      }});
      {"" if not dept_breakdown else f'''
      new Chart(document.getElementById("dept-chart"), {{
        type: "doughnut",
        data: {{ labels: {dept_labels}, datasets: [{{ data: {dept_values}, backgroundColor: {dept_colors}, borderWidth: 0 }}] }},
        options: {{ plugins: {{ legend: {{ display: false }} }}, cutout: "65%" }},
      }});
      '''}
    </script>
    """

    if recent_appointments:
        recent_rows = "".join(
            f"""<tr>
              <td>{html.escape(a.scheduled_at.strftime('%d %b %Y, %H:%M'))}</td>
              <td>{html.escape(a.phone)}</td>
              <td>{html.escape(a.doctor_name)}</td>
              <td>{html.escape(a.department_name)}</td>
              <td><span class="pill pill-{a.status}">{a.status}</span></td>
              <td><span class="pill pill-source-{a.source}">{'Walk-in' if a.source == 'staff' else 'WhatsApp'}</span></td>
            </tr>"""
            for a in recent_appointments
        )
        recent_table = f"""
        <table>
          <thead><tr><th>Time</th><th>Patient</th><th>Doctor</th><th>Department</th><th>Status</th><th>Source</th></tr></thead>
          <tbody>{recent_rows}</tbody>
        </table>
        """
    else:
        recent_table = '<div class="empty-note">No appointments yet.</div>'

    if activity_feed:
        activity_rows = "".join(
            f"""<div class="activity-row">
              <span class="activity-row-main">{html.escape(event['label'])} — {html.escape(event['phone'])}
                ({html.escape(event['doctor_name'])}, {html.escape(event['department_name'])})</span>
              <span class="activity-row-time">{html.escape(event['at'].strftime('%d %b, %H:%M'))}</span>
            </div>"""
            for event in activity_feed
        )
    else:
        activity_rows = '<div class="empty-note">No recent activity.</div>'

    return f"""<!doctype html>
<html>
<head><title>Dashboard — {html.escape(hospital.name)}</title>{_STYLE}
<style>table {{ width: 100%; border-collapse: collapse; }} th {{ text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint); padding: 8px 10px; border-bottom: 1px solid var(--sage-line); }} td {{ padding: 10px; border-bottom: 1px solid var(--sage-line); font-size: 13.5px; }}</style>
</head>
<body>
<div class="dashboard-shell">
  {_dashboard_sidebar_html(hospital, "dashboard")}
  <main class="dashboard-main">
    <div class="page-header">
      <h2>Dashboard</h2>
      <span class="hint">Welcome back — here's what's happening at {html.escape(hospital.name)} today.</span>
    </div>
    {stat_tiles}
    {charts}
    <h3 class="dashboard-section-title" style="margin-top:8px;">Recent Appointments</h3>
    {recent_table}
    <h3 class="dashboard-section-title" style="margin-top:32px;">Recent Activity</h3>
    {activity_rows}
  </main>
</div>
</body>
</html>"""


def _new_booking_html(
    hospital, departments: list[dict], doctors_by_department: dict[str, list[dict]],
    slots_by_doctor: dict[str, dict[str, list[dict]]], errors: list[str] | None = None,
    values: dict | None = None,
) -> str:
    """Section 12.9: staff-created bookings -- walk-ins or phone bookings a
    front-desk staff member enters on the patient's behalf, going through the
    exact same connector.create_booking()/availability logic as a WhatsApp
    booking (portal_new_booking_submit() below), not a separate path.

    Branch selection is a deliberate no-op single-value dropdown -- this
    codebase has no branch/location model anywhere (every hospital row is one
    location; SPEC Section 4's data model has no such table), and building
    one was explicitly out of scope for this task. Flagged here and in
    Spec.md, not silently assumed away.

    doctors_by_department / slots_by_doctor are embedded as JSON (same
    bootstrap-JSON pattern admin/onboarding.py's wizard already uses) so the
    department -> doctor -> date -> available-slots cascade is pure
    client-side filtering, no extra server round-trip per selection --
    reasonable for one hospital's small doctor/slot-window scale (Section
    14.7's existing 14-day rolling window)."""
    v = values or {}
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error-banner"><strong>Please fix the following:</strong><ul>{items}</ul></div>'

    dept_options = "".join(
        f'<option value="{d["id"]}"{" selected" if v.get("department_id") == d["id"] else ""}>{html.escape(d["name"])}</option>'
        for d in departments
    )

    doctors_json = json.dumps(doctors_by_department).replace("</", "<\\/")
    slots_json = json.dumps(slots_by_doctor).replace("</", "<\\/")

    return f"""<!doctype html>
<html>
<head><title>New Booking — {html.escape(hospital.name)}</title>{_STYLE}
<style>
  select {{ width: 100%; font-family: var(--font-body); font-size: 14px; padding: 10px 12px; border: 1px solid var(--sage-line); border-radius: 8px; background: var(--paper); color: var(--ink); margin-top: 6px; }}
  select:disabled {{ color: var(--ink-faint); background: var(--sage-line); }}
  #search-results {{ margin-top: 6px; }}
  .search-result-row {{ padding: 8px 12px; border: 1px solid var(--sage-line); border-radius: 8px; margin-top: 6px; cursor: pointer; font-size: 13.5px; background: var(--card); }}
  .search-result-row:hover {{ background: var(--success-tint); }}
  .selected-patient {{ margin-top: 8px; font-size: 13px; color: var(--sage-deep); font-weight: 600; }}
</style>
</head>
<body>
<div class="dashboard-shell">
  {_dashboard_sidebar_html(hospital, "new-booking")}
  <main class="dashboard-main">
    {error_html}
    <div class="page-header"><h2>New Booking</h2></div>
    <p class="step-desc">For walk-in or phone patients — creates a real appointment through the same availability check WhatsApp bookings use, so it can never double-book against one.</p>
    <div class="main" style="max-width: 640px;">
      <form method="post" action="/portal/new-booking" id="new-booking-form">
        <label>Search existing patients (by name or phone)</label>
        <input type="text" id="patient-search" placeholder="Start typing a name or phone number...">
        <div id="search-results"></div>
        <div id="selected-patient" class="selected-patient" style="display:none;"></div>

        <div class="field-row">
          <div>
            <label for="patient_name">Patient name</label>
            <input type="text" id="patient_name" name="patient_name" value="{html.escape(v.get('patient_name', ''))}">
            <p class="field-hint">Leave existing patients' names as-is, or fill this in if it's not on file yet.</p>
          </div>
          <div>
            <label for="patient_phone">Patient phone</label>
            <input type="text" id="patient_phone" name="patient_phone" value="{html.escape(v.get('patient_phone', ''))}" required>
          </div>
        </div>

        <label>Branch</label>
        <select disabled>
          <option selected>Main Branch — {html.escape(hospital.name)}</option>
        </select>
        <p class="field-hint">This hospital isn't set up with multiple branches/locations yet — every booking is against its one location.</p>

        <div class="field-row">
          <div>
            <label for="department_id">Department</label>
            <select id="department_id" name="department_id" required>
              <option value="">Choose a department</option>
              {dept_options}
            </select>
          </div>
          <div>
            <label for="doctor_id">Doctor</label>
            <select id="doctor_id" name="doctor_id" required disabled>
              <option value="">Choose a department first</option>
            </select>
          </div>
        </div>

        <div class="field-row">
          <div>
            <label for="booking-date">Date</label>
            <input type="date" id="booking-date" disabled>
          </div>
          <div>
            <label for="slot_id">Available slot</label>
            <select id="slot_id" name="slot_id" required disabled>
              <option value="">Choose a doctor and date first</option>
            </select>
          </div>
        </div>

        <div class="nav-buttons">
          <a class="btn-secondary" href="/portal/dashboard">Cancel</a>
          <button type="submit">Create booking</button>
        </div>
      </form>
    </div>
  </main>
</div>
<script>
(function () {{
  var DOCTORS_BY_DEPT = {doctors_json};
  var SLOTS_BY_DOCTOR = {slots_json};

  var deptSelect = document.getElementById("department_id");
  var doctorSelect = document.getElementById("doctor_id");
  var dateInput = document.getElementById("booking-date");
  var slotSelect = document.getElementById("slot_id");

  function populateDoctors() {{
    var doctors = DOCTORS_BY_DEPT[deptSelect.value] || [];
    doctorSelect.innerHTML = "";
    if (!doctors.length) {{
      doctorSelect.innerHTML = '<option value="">No doctors in this department</option>';
      doctorSelect.disabled = true;
    }} else {{
      doctorSelect.innerHTML = '<option value="">Choose a doctor</option>' +
        doctors.map(function (d) {{ return '<option value="' + d.id + '">' + d.name + '</option>'; }}).join("");
      doctorSelect.disabled = false;
    }}
    dateInput.value = ""; dateInput.disabled = true;
    resetSlots("Choose a doctor and date first");
  }}

  function resetSlots(placeholder) {{
    slotSelect.innerHTML = '<option value="">' + placeholder + '</option>';
    slotSelect.disabled = true;
  }}

  function populateSlots() {{
    var doctorSlots = SLOTS_BY_DOCTOR[doctorSelect.value] || {{}};
    var daySlots = doctorSlots[dateInput.value] || [];
    if (!daySlots.length) {{
      resetSlots("No available slots that day");
      return;
    }}
    slotSelect.innerHTML = daySlots.map(function (s) {{ return '<option value="' + s.id + '">' + s.label + '</option>'; }}).join("");
    slotSelect.disabled = false;
  }}

  deptSelect.addEventListener("change", populateDoctors);
  doctorSelect.addEventListener("change", function () {{
    dateInput.value = "";
    dateInput.disabled = !doctorSelect.value;
    resetSlots("Choose a date");
  }});
  dateInput.addEventListener("change", populateSlots);

  // --- Patient search (Section 12.9) ---
  var searchBox = document.getElementById("patient-search");
  var resultsBox = document.getElementById("search-results");
  var selectedBox = document.getElementById("selected-patient");
  var nameField = document.getElementById("patient_name");
  var phoneField = document.getElementById("patient_phone");
  var searchTimer = null;

  searchBox.addEventListener("input", function () {{
    clearTimeout(searchTimer);
    var q = searchBox.value.trim();
    if (!q) {{ resultsBox.innerHTML = ""; return; }}
    searchTimer = setTimeout(function () {{
      fetch("/portal/patients/search?q=" + encodeURIComponent(q))
        .then(function (r) {{ return r.ok ? r.json() : []; }})
        .then(function (results) {{
          if (!results.length) {{ resultsBox.innerHTML = '<div class="field-hint">No matching patients — fill in the fields below to add a new one.</div>'; return; }}
          resultsBox.innerHTML = "";
          results.forEach(function (p) {{
            var row = document.createElement("div");
            row.className = "search-result-row";
            row.textContent = (p.name || "(no name on file)") + " — " + p.phone;
            row.addEventListener("click", function () {{
              nameField.value = p.name || "";
              phoneField.value = p.phone;
              selectedBox.style.display = "block";
              selectedBox.textContent = "Selected: " + (p.name || "(no name on file)") + " — " + p.phone;
              resultsBox.innerHTML = "";
              searchBox.value = "";
            }});
            resultsBox.appendChild(row);
          }});
        }});
    }}, 250);
  }});
}})();
</script>
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
              <td><span class="pill pill-source-{a.source}">{'Walk-in' if a.source == 'staff' else 'WhatsApp'}</span></td>
            </tr>"""
            for a in appointments
        )
        table = f"""<table>
          <thead><tr><th>Scheduled for</th><th>Patient phone</th><th>Department</th><th>Doctor</th><th>Status</th><th>Source</th></tr></thead>
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
    template-cloning JS machinery for what's a single-doctor-at-a-time page.

    Section 14.7: breaks gets the same fixed-single-row treatment as shifts
    (one optional break window, e.g. lunch, covers the vast majority of real
    schedules) -- applies uniformly to every working day checked above, same
    as the wizard's version (db/schema.sql's comment on doctors.breaks)."""
    doctor = doctor or {}
    days = set(doctor.get("working_days") or [])
    hours = doctor.get("working_hours") or []
    shift1 = hours[0].split("-") if len(hours) > 0 else ["", ""]
    shift2 = hours[1].split("-") if len(hours) > 1 else ["", ""]
    breaks = doctor.get("breaks") or []
    break1 = breaks[0].split("-") if len(breaks) > 0 else ["", ""]

    days_html = "".join(
        f'<label class="checkbox-row"><input type="checkbox" name="working_days" value="{d}" '
        f'{"checked" if d in days else ""}> {d}</label>'
        for d in _WEEKDAY_ABBREVS
    )

    def _num(value) -> str:
        return "" if value is None else str(value)

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
      <div class="field-row">
        <div>
          <label>Slot duration (minutes)</label>
          <input type="number" min="1" name="slot_duration_minutes" value="{doctor.get('slot_duration_minutes') or 30}">
          <p class="field-hint">How long each appointment lasts — e.g. 20 means a new bookable slot every 20 minutes.</p>
        </div>
        <div>
          <label>Break (optional)</label>
          <div class="shift-row">
            <input type="time" name="break1_start" value="{html.escape(break1[0])}">
            <span class="shift-sep">to</span>
            <input type="time" name="break1_end" value="{html.escape(break1[1])}">
          </div>
          <p class="field-hint">Excluded from bookable slots, e.g. lunch. Applies every working day.</p>
        </div>
      </div>
      <div class="field-row">
        <div>
          <label>Bookings per slot</label>
          <input type="number" min="1" name="max_bookings_per_slot" value="{doctor.get('max_bookings_per_slot') or 1}">
          <p class="field-hint">How many patients can book the exact same slot time. 1 = normal behavior.</p>
        </div>
        <div>
          <label>Daily booking limit (optional)</label>
          <input type="number" min="0" name="daily_booking_limit" value="{_num(doctor.get('daily_booking_limit'))}">
        </div>
      </div>
      <div class="field-row">
        <div>
          <label>Online quota (optional)</label>
          <input type="number" min="0" name="online_quota" value="{_num(doctor.get('online_quota'))}">
        </div>
        <div>
          <label>Walk-in quota (optional)</label>
          <input type="number" min="0" name="walkin_quota" value="{_num(doctor.get('walkin_quota'))}">
          <p class="field-hint">Reserved WhatsApp/front-desk split of the daily limit. Not enforced until walk-in booking exists.</p>
        </div>
      </div>
      <div class="field-row">
        <div>
          <label>Follow-up duration (minutes, optional)</label>
          <input type="number" min="1" name="followup_duration_minutes" value="{doctor.get('followup_duration_minutes') or ''}">
        </div>
        <div>
          <label>Schedule effective from (optional)</label>
          <input type="date" name="effective_from" value="{html.escape(doctor.get('effective_from') or '')}">
          <p class="field-hint">Leave blank for "effective immediately." A future date keeps already-offered earlier slots untouched.</p>
        </div>
      </div>
    """


def _doctors_html(
    hospital, departments: list[dict], doctors: list[dict],
    errors: list[str] | None = None, warnings: list[str] | None = None,
) -> str:
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error-banner"><strong>Please fix the following:</strong><ul>{items}</ul></div>'
    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
        error_html += f'<div class="warning-banner"><strong>Worth double-checking:</strong><ul>{items}</ul></div>'

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


def _doctor_leave_html(doctor_id: str, leave: list[dict]) -> str:
    """Section 14.7: whole-day unavailability management -- lives only on the
    edit page (not onboarding), since a brand-new doctor has no known leave
    dates yet. generate_slots_for_doctor() skips every date listed here."""
    if leave:
        rows = "".join(
            f"""<div class="list-row">
              <div class="list-row-main">
                <span class="list-row-title">{html.escape(row['date'])}</span>
                <span class="list-row-sub">{html.escape(row['reason']) if row.get('reason') else ''}</span>
              </div>
              <div class="list-row-meta">
                <form method="post" action="/portal/doctors/{doctor_id}/leave/{row['id']}/delete" style="margin:0;">
                  <button type="submit" class="btn-secondary small">Remove</button>
                </form>
              </div>
            </div>"""
            for row in leave
        )
        leave_list = f'<div class="card-list">{rows}</div>'
    else:
        leave_list = '<div class="empty-note">No leave dates recorded.</div>'

    return f"""
    <h3 style="margin-top: 32px; font-family: var(--font-body); font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint);">Leave / days off</h3>
    {leave_list}
    <form method="post" action="/portal/doctors/{doctor_id}/leave" style="margin-top: 12px;">
      <div class="field-row">
        <div><input type="date" name="date" required></div>
        <div><input type="text" name="reason" placeholder="Reason (optional)"></div>
        <div><button type="submit" class="small" style="width:auto;">+ Add leave date</button></div>
      </div>
    </form>
    """


def _doctor_edit_html(
    hospital, doctor: dict, errors: list[str] | None = None,
    warnings: list[str] | None = None, leave: list[dict] | None = None,
) -> str:
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error-banner"><strong>Please fix the following:</strong><ul>{items}</ul></div>'
    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
        error_html += f'<div class="warning-banner"><strong>Worth double-checking:</strong><ul>{items}</ul></div>'

    leave_html = _doctor_leave_html(doctor["id"], leave or []) if "id" in doctor else ""

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
    {leave_html}
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
    response = RedirectResponse(url="/portal/dashboard", status_code=303)
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


@router.get("/portal/dashboard", response_class=HTMLResponse)
async def portal_dashboard(request: Request):
    """Section 12.8: the default landing page after login (see
    portal_login_submit() above) -- /portal/bookings, /portal/doctors, and
    /portal/settings are unchanged, still reachable via the sidebar."""
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    stats = db.get_dashboard_stats(hospital.id)
    weekly_counts = db.get_weekly_appointment_counts(hospital.id)
    dept_breakdown = db.get_appointments_by_department(hospital.id)
    recent_appointments = db.get_all_appointments_for_hospital(hospital.id, limit=10)
    activity_feed = db.get_recent_activity_feed(hospital.id, limit=10)
    return _dashboard_html(hospital, stats, weekly_counts, dept_breakdown, recent_appointments, activity_feed)


def _build_new_booking_context(hospital) -> tuple[list[dict], dict, dict]:
    """Shared by the GET (blank form) and POST (re-render on error) handlers
    below -- departments/doctors/available-slots, all hospital-scoped and all
    read through the SAME connector interface (Section 12.6.2) the WhatsApp
    flow uses, not a parallel query path."""
    connector = connectors.get_connector_for_hospital(hospital)
    departments = connector.get_departments(hospital.id)
    doctors_by_department: dict[str, list[dict]] = {}
    slots_by_doctor: dict[str, dict[str, list[dict]]] = {}
    for dept in departments:
        doctors = connector.get_doctors(hospital.id, dept["id"])
        doctors_by_department[dept["id"]] = doctors
        for doc in doctors:
            slots = connector.get_available_slots(hospital.id, doc["id"])
            by_date: dict[str, list[dict]] = {}
            for s in slots:
                by_date.setdefault(s["date"], []).append({"id": s["id"], "label": s["label"]})
            slots_by_doctor[doc["id"]] = by_date
    return departments, doctors_by_department, slots_by_doctor


@router.get("/portal/new-booking", response_class=HTMLResponse)
async def portal_new_booking_form(request: Request):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    departments, doctors_by_department, slots_by_doctor = _build_new_booking_context(hospital)
    return _new_booking_html(hospital, departments, doctors_by_department, slots_by_doctor)


@router.post("/portal/new-booking", response_class=HTMLResponse)
async def portal_new_booking_submit(
    request: Request,
    patient_name: str = Form(""),
    patient_phone: str = Form(""),
    department_id: str = Form(""),
    doctor_id: str = Form(""),
    slot_id: str = Form(""),
):
    """Section 12.9: creates a real appointment through connector.create_booking()
    -- the EXACT same call core/booking_flow.py's WhatsApp confirm step makes
    -- with source="staff", so it's protected by the exact same availability/
    double-booking/quota logic (db.create_appointment(), Section 12.9's
    per-(doctor,date) advisory lock), not a separate path that could race
    against a WhatsApp booking."""
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)

    departments, doctors_by_department, slots_by_doctor = _build_new_booking_context(hospital)
    values = {"patient_name": patient_name, "patient_phone": patient_phone, "department_id": department_id}

    errors = []
    patient_phone = patient_phone.strip()
    if not db.is_valid_phone(patient_phone):
        errors.append("Patient phone is required and must contain at least one digit.")
    department = db.find_department(hospital.id, department_id)
    if department is None:
        errors.append("Choose a valid department.")
    doctor = db.find_doctor(hospital.id, department_id, doctor_id) if department else None
    if doctor is None:
        errors.append("Choose a valid doctor.")
    scheduled_at = None
    if not slot_id:
        errors.append("Choose an available slot.")
    else:
        try:
            scheduled_at = datetime.fromisoformat(slot_id)
        except ValueError:
            errors.append("That slot is no longer valid — pick another.")

    if errors:
        return HTMLResponse(
            _new_booking_html(hospital, departments, doctors_by_department, slots_by_doctor, errors, values),
            status_code=400,
        )

    connector = connectors.get_connector_for_hospital(hospital)
    try:
        connector.create_booking(
            hospital.id, patient_phone, department_id, doctor_id, scheduled_at,
            source=db.SOURCE_STAFF, patient_name=patient_name.strip() or None,
        )
    except db.QuotaExceededError as e:
        return HTMLResponse(
            _new_booking_html(hospital, departments, doctors_by_department, slots_by_doctor, [str(e)], values),
            status_code=400,
        )
    except IntegrityError:
        return HTMLResponse(
            _new_booking_html(
                hospital, departments, doctors_by_department, slots_by_doctor,
                ["That slot was just taken — please pick another."], values,
            ),
            status_code=400,
        )

    return RedirectResponse(url="/portal/bookings", status_code=303)


@router.get("/portal/patients/search")
async def portal_patients_search(request: Request, q: str = ""):
    hospital = _current_hospital(request)
    if hospital is None:
        return JSONResponse([], status_code=401)
    return JSONResponse(db.search_patients(hospital.id, q))


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


def _build_breaks(break1_start: str, break1_end: str) -> str:
    """Same convention as _build_working_hours() above, for the portal's
    single fixed (optional) break window (Section 14.7)."""
    return f"{break1_start}-{break1_end}" if break1_start and break1_end else ""


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
    break1_start: str = Form(""),
    break1_end: str = Form(""),
    max_bookings_per_slot: str = Form("1"),
    daily_booking_limit: str = Form(""),
    online_quota: str = Form(""),
    walkin_quota: str = Form(""),
    followup_duration_minutes: str = Form(""),
    effective_from: str = Form(""),
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
    breaks_raw = _build_breaks(break1_start, break1_end)
    doctor_data, errors, warnings = _validate_doctor_fields(
        0, name, specialization, qualification, years_experience, ",".join(working_days), hours_raw, slot_duration_minutes,
        breaks_raw, max_bookings_per_slot, daily_booking_limit, online_quota, walkin_quota,
        followup_duration_minutes, effective_from,
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
        breaks=doctor_data["breaks"],
        max_bookings_per_slot=doctor_data["max_bookings_per_slot"],
        daily_booking_limit=doctor_data["daily_booking_limit"],
        online_quota=doctor_data["online_quota"],
        walkin_quota=doctor_data["walkin_quota"],
        followup_duration_minutes=doctor_data["followup_duration_minutes"],
        effective_from=doctor_data["effective_from"],
    )
    if warnings:
        departments = db.get_departments(hospital.id)
        doctors = db.get_all_doctors_for_hospital(hospital.id)
        return HTMLResponse(_doctors_html(hospital, departments, doctors, warnings=warnings))
    return RedirectResponse(url="/portal/doctors", status_code=303)


@router.get("/portal/doctors/{doctor_id}/edit", response_class=HTMLResponse)
async def portal_edit_doctor_form(doctor_id: str, request: Request):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return HTMLResponse("<p>No such doctor.</p>", status_code=404)
    leave = db.get_doctor_leave(hospital.id, doctor_id)
    return _doctor_edit_html(hospital, doctor, leave=leave)


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
    break1_start: str = Form(""),
    break1_end: str = Form(""),
    max_bookings_per_slot: str = Form("1"),
    daily_booking_limit: str = Form(""),
    online_quota: str = Form(""),
    walkin_quota: str = Form(""),
    followup_duration_minutes: str = Form(""),
    effective_from: str = Form(""),
):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)

    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return HTMLResponse("<p>No such doctor.</p>", status_code=404)

    hours_raw = _build_working_hours(shift1_start, shift1_end, shift2_start, shift2_end)
    breaks_raw = _build_breaks(break1_start, break1_end)
    doctor_data, errors, warnings = _validate_doctor_fields(
        0, name, specialization, qualification, years_experience, ",".join(working_days), hours_raw, slot_duration_minutes,
        breaks_raw, max_bookings_per_slot, daily_booking_limit, online_quota, walkin_quota,
        followup_duration_minutes, effective_from,
    )
    if errors:
        submitted = {
            "id": doctor_id, "name": name, "specialization": specialization, "qualification": qualification,
            "years_experience": years_experience, "working_days": working_days,
            "working_hours": [r for r in hours_raw.split(",") if r],
            "slot_duration_minutes": slot_duration_minutes,
            "breaks": [r for r in breaks_raw.split(",") if r],
            "max_bookings_per_slot": max_bookings_per_slot, "daily_booking_limit": daily_booking_limit,
            "online_quota": online_quota, "walkin_quota": walkin_quota,
            "followup_duration_minutes": followup_duration_minutes, "effective_from": effective_from,
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
        breaks=doctor_data["breaks"],
        max_bookings_per_slot=doctor_data["max_bookings_per_slot"],
        daily_booking_limit=doctor_data["daily_booking_limit"],
        online_quota=doctor_data["online_quota"],
        walkin_quota=doctor_data["walkin_quota"],
        followup_duration_minutes=doctor_data["followup_duration_minutes"],
        effective_from=doctor_data["effective_from"],
    )
    if warnings:
        updated = db.get_doctor_full(hospital.id, doctor_id)
        leave = db.get_doctor_leave(hospital.id, doctor_id)
        return HTMLResponse(_doctor_edit_html(hospital, updated, warnings=warnings, leave=leave))
    return RedirectResponse(url="/portal/doctors", status_code=303)


@router.post("/portal/doctors/{doctor_id}/leave", response_class=HTMLResponse)
async def portal_add_doctor_leave(doctor_id: str, request: Request, date: str = Form(""), reason: str = Form("")):
    """Section 14.7: mark a whole day off for this doctor -- generate_slots_for_doctor()
    skips it entirely on the next regeneration (done immediately by
    db.create_doctor_leave()), not something staff manage during initial
    onboarding (there's nothing to know yet), so this only lives here."""
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    doctor = db.get_doctor_full(hospital.id, doctor_id)
    if doctor is None:
        return HTMLResponse("<p>No such doctor.</p>", status_code=404)

    date = date.strip()
    if not date:
        leave = db.get_doctor_leave(hospital.id, doctor_id)
        return HTMLResponse(_doctor_edit_html(hospital, doctor, ["A leave date is required."], leave=leave), status_code=400)
    try:
        _date.fromisoformat(date)
    except ValueError:
        leave = db.get_doctor_leave(hospital.id, doctor_id)
        return HTMLResponse(_doctor_edit_html(hospital, doctor, [f'"{date}" is not a valid date (use YYYY-MM-DD).'], leave=leave), status_code=400)

    db.create_doctor_leave(hospital.id, doctor_id, date, reason.strip() or None)
    return RedirectResponse(url=f"/portal/doctors/{doctor_id}/edit", status_code=303)


@router.post("/portal/doctors/{doctor_id}/leave/{leave_id}/delete", response_class=HTMLResponse)
async def portal_delete_doctor_leave(doctor_id: str, leave_id: int, request: Request):
    hospital = _current_hospital(request)
    if hospital is None:
        return RedirectResponse(url="/portal/login", status_code=303)
    db.delete_doctor_leave(hospital.id, doctor_id, leave_id)
    return RedirectResponse(url=f"/portal/doctors/{doctor_id}/edit", status_code=303)
