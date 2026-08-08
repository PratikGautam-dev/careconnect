# admin/onboarding.py
"""
Guided onboarding wizard (SPEC Section 12.1, Phase 10; multi-step rebuild).
A single server-rendered page with client-side (vanilla JS, no framework —
"minimal maintenance" per the project's own priorities) step navigation: a
left rail showing all 8 steps with active/done state, informational steps
with external links (1-3), credential fields (4-5), the Tier 1/2/3 decision
(6), repeatable doctor-card inputs (7), and a review step before the one real
POST that actually submits everything (8) — the multi-step UI is a
presentation layer over a single <form>; nothing here talks to the backend
until that one submit.

This is still v1 of the guided wizard, not the later Embedded Signup flow
(Section 12.5) — the operator still enters the hospital's own Meta
credentials by hand (Section 12.3's constraint: the hospital's own Meta
business/number setup, verification, and System User token must already
exist before this form is used; this form does not create any of that).

Protected by a shared secret (ADMIN_SECRET env var), same pattern as
core/main.py's INTERNAL_SECRET — basic protection against an unauthenticated
stranger creating hospital rows (and storing real API credentials) on a
deployed instance, not a full auth system. Entered on the final review step,
next to the Submit button, but validated server-side regardless of anything
the client does.
"""
import hmac
import html
import json
import os
import re
from datetime import date, datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

import core.rate_limit as rate_limit
import db.repository as db
import flows
from admin.theme import STYLE as _STYLE
from db.connection import IntegrityError

router = APIRouter()

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def check_admin_secret(secret: str, request: Request) -> bool:
    """Timing-safe (hmac.compare_digest) and rate-limited (audit follow-up,
    Spec.md Section 0) -- shared by every ADMIN_SECRET check in this module
    plus admin/onboarding_api.py's JSON equivalent, so the lockout is one
    counter per caller IP regardless of which of the two entry points
    (HTML wizard vs JSON API) they're hitting."""
    key = rate_limit.client_key("admin_secret", request)
    if rate_limit.is_locked_out(key):
        return False
    ok = bool(ADMIN_SECRET) and hmac.compare_digest(secret or "", ADMIN_SECRET)
    if ok:
        rate_limit.reset(key)
    else:
        rate_limit.record_failure(key)
    return ok

_WEEKDAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_WEEKDAY_SET = set(_WEEKDAY_ABBREVS)
_TIME_RANGE_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
_VALID_TIERS = {"tier1", "tier2", "tier3"}


# --- Validation (unchanged rules from the textarea-DSL version — same fields,
# same constraints, just read from structured per-doctor form inputs now) ---

def _split_time_range(r: str) -> tuple[str, str]:
    """Only ever called on a string already confirmed to match _TIME_RANGE_RE."""
    start, end = r.split("-")
    return start, end


def _minutes_between(start: str, end: str) -> int:
    fmt = "%H:%M"
    return int((datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds() // 60)


def _validate_doctor_fields(
    index: int, name: str, specialization: str, qualification: str,
    years_raw: str, days_raw: str, hours_raw: str, duration_raw: str,
    breaks_raw: str = "", max_bookings_raw: str = "1", daily_limit_raw: str = "",
    online_quota_raw: str = "", walkin_quota_raw: str = "",
    followup_duration_raw: str = "", effective_from_raw: str = "",
) -> tuple[dict | None, list[str], list[str]]:
    """Returns (doctor_dict_or_None, errors, warnings). errors block
    submission (same as before Section 14.7); warnings (currently just the
    online/walk-in quota vs. daily_booking_limit check) don't -- the caller
    still gets a doctor dict back alongside them."""
    errors = []
    warnings = []
    name = name.strip()
    label = f"Doctor #{index + 1}" + (f" ({name})" if name else "")
    if not name:
        errors.append(f"Doctor #{index + 1}: name is required.")

    years_experience = None
    years_raw = years_raw.strip()
    if years_raw:
        try:
            years_experience = int(years_raw)
        except ValueError:
            errors.append(f'{label}: years of experience "{years_raw}" is not a whole number.')

    working_days = [d.strip() for d in days_raw.split(",") if d.strip()]
    if not working_days:
        errors.append(f"{label}: at least one working day is required.")
    else:
        bad_days = [d for d in working_days if d not in _WEEKDAY_SET]
        if bad_days:
            errors.append(f"{label}: invalid working day(s) {bad_days} — use Mon,Tue,Wed,Thu,Fri,Sat,Sun.")

    working_hours = [h.strip() for h in hours_raw.split(",") if h.strip()]
    if not working_hours:
        errors.append(f"{label}: at least one working hour range is required (e.g. 10:00-13:00).")
    else:
        bad_ranges = [h for h in working_hours if not _TIME_RANGE_RE.match(h)]
        if bad_ranges:
            errors.append(f"{label}: invalid working hour range(s) {bad_ranges} — use HH:MM-HH:MM.")

    slot_duration_minutes = None
    duration_raw = duration_raw.strip()
    if not duration_raw:
        errors.append(f"{label}: slot duration (minutes) is required.")
    else:
        try:
            slot_duration_minutes = int(duration_raw)
            if slot_duration_minutes <= 0:
                raise ValueError
        except ValueError:
            errors.append(f'{label}: slot duration "{duration_raw}" must be a positive whole number.')

    # --- Section 14.7 fields ---

    breaks = [b.strip() for b in breaks_raw.split(",") if b.strip()]
    if breaks:
        bad_break_ranges = [b for b in breaks if not _TIME_RANGE_RE.match(b)]
        if bad_break_ranges:
            errors.append(f"{label}: invalid break range(s) {bad_break_ranges} — use HH:MM-HH:MM.")
        elif working_hours and not bad_ranges:
            # Breaks apply to every working day uniformly (db/schema.sql's
            # comment on doctors.breaks), so there's only one set of shifts to
            # check each break against, not one per specific day.
            parsed_shifts = [_split_time_range(h) for h in working_hours]
            parsed_breaks = [_split_time_range(b) for b in breaks]

            outside_shift = [
                breaks[i] for i, pb in enumerate(parsed_breaks)
                if not any(s[0] <= pb[0] and pb[1] <= s[1] for s in parsed_shifts)
            ]
            if outside_shift:
                errors.append(f"{label}: break(s) {outside_shift} must fall entirely within a working-hours shift.")

            sorted_breaks = sorted(parsed_breaks)
            for a, b in zip(sorted_breaks, sorted_breaks[1:]):
                if a[1] > b[0]:
                    errors.append(f"{label}: break windows must not overlap each other.")
                    break

            if slot_duration_minutes and not outside_shift:
                for shift in parsed_shifts:
                    shift_minutes = _minutes_between(shift[0], shift[1])
                    break_minutes = sum(
                        _minutes_between(pb[0], pb[1]) for pb in parsed_breaks
                        if shift[0] <= pb[0] and pb[1] <= shift[1]
                    )
                    if shift_minutes - break_minutes < slot_duration_minutes:
                        errors.append(f"{label}: breaks leave no bookable time in shift {shift[0]}-{shift[1]}.")

    max_bookings_per_slot = 1
    max_bookings_raw = (max_bookings_raw or "1").strip()
    try:
        max_bookings_per_slot = int(max_bookings_raw)
        if max_bookings_per_slot < 1:
            raise ValueError
    except ValueError:
        errors.append(f'{label}: "bookings per slot" must be a whole number of at least 1.')

    daily_booking_limit = None
    daily_limit_raw = (daily_limit_raw or "").strip()
    if daily_limit_raw:
        try:
            daily_booking_limit = int(daily_limit_raw)
            if daily_booking_limit < 0:
                raise ValueError
        except ValueError:
            errors.append(f'{label}: daily booking limit must be a whole number of 0 or more.')

    def _parse_optional_nonneg_int(raw: str, field_label: str) -> int | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            value = int(raw)
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            errors.append(f"{label}: {field_label} must be a whole number of 0 or more.")
            return None

    online_quota = _parse_optional_nonneg_int(online_quota_raw, "online quota")
    walkin_quota = _parse_optional_nonneg_int(walkin_quota_raw, "walk-in quota")
    if online_quota is not None and walkin_quota is not None and daily_booking_limit is not None:
        if online_quota + walkin_quota > daily_booking_limit:
            warnings.append(
                f"{label}: online quota ({online_quota}) + walk-in quota ({walkin_quota}) exceeds the "
                f"daily booking limit ({daily_booking_limit}) — this is allowed (intentional headroom is fine), "
                "just confirm it's not a mistake."
            )

    followup_duration_minutes = _parse_optional_nonneg_int(followup_duration_raw, "follow-up duration")
    if followup_duration_minutes == 0:
        errors.append(f"{label}: follow-up duration must be a positive whole number, not 0.")

    effective_from = None
    effective_from_raw = (effective_from_raw or "").strip()
    if effective_from_raw:
        try:
            date.fromisoformat(effective_from_raw)
            effective_from = effective_from_raw
        except ValueError:
            errors.append(f'{label}: "effective from" date "{effective_from_raw}" is not a valid date (use YYYY-MM-DD).')

    if errors:
        return None, errors, warnings

    return {
        "name": name,
        "specialization": specialization.strip() or None,
        "qualification": qualification.strip() or None,
        "years_experience": years_experience,
        "working_days": working_days,
        "working_hours": working_hours,
        "slot_duration_minutes": slot_duration_minutes,
        "breaks": breaks,
        "max_bookings_per_slot": max_bookings_per_slot,
        "daily_booking_limit": daily_booking_limit,
        "online_quota": online_quota,
        "walkin_quota": walkin_quota,
        "followup_duration_minutes": followup_duration_minutes,
        "effective_from": effective_from,
    }, [], warnings


def _build_departments(
    department_name: list[str],
    doctor_department_index: list[str],
    doctor_name: list[str],
    doctor_specialization: list[str],
    doctor_qualification: list[str],
    doctor_years_experience: list[str],
    doctor_working_days: list[str],
    doctor_working_hours: list[str],
    doctor_slot_duration_minutes: list[str],
    doctor_breaks: list[str] | None = None,
    doctor_max_bookings_per_slot: list[str] | None = None,
    doctor_daily_booking_limit: list[str] | None = None,
    doctor_online_quota: list[str] | None = None,
    doctor_walkin_quota: list[str] | None = None,
    doctor_followup_duration_minutes: list[str] | None = None,
    doctor_effective_from: list[str] | None = None,
) -> tuple[list[dict], list[str], list[str]]:
    """Reconstructs department/doctor structures from the wizard's repeatable
    doctor-card fields (Step 7) — parallel arrays positioned in DOM submit
    order, with doctor_department_index[i] naming which department_name[]
    entry doctor i belongs to (recomputed by the page's JS immediately before
    submit, so it always reflects current on-screen card order/removals).
    Returns (departments, errors, warnings) -- Section 14.7's quota-vs-limit
    check is a warning, not an error (see _validate_doctor_fields)."""
    departments = [{"name": n.strip(), "doctors": []} for n in department_name]
    errors: list[str] = []
    warnings: list[str] = []
    doctor_breaks = doctor_breaks or []
    doctor_max_bookings_per_slot = doctor_max_bookings_per_slot or []
    doctor_daily_booking_limit = doctor_daily_booking_limit or []
    doctor_online_quota = doctor_online_quota or []
    doctor_walkin_quota = doctor_walkin_quota or []
    doctor_followup_duration_minutes = doctor_followup_duration_minutes or []
    doctor_effective_from = doctor_effective_from or []

    def _at(lst: list[str], i: int) -> str:
        return lst[i] if i < len(lst) else ""

    for i in range(len(doctor_name)):
        idx_raw = doctor_department_index[i] if i < len(doctor_department_index) else ""
        try:
            dept_idx = int(idx_raw)
        except ValueError:
            errors.append(f"Doctor #{i + 1} is missing a valid department assignment.")
            continue
        if not (0 <= dept_idx < len(departments)):
            errors.append(f"Doctor #{i + 1} references an invalid department.")
            continue

        doctor, doc_errors, doc_warnings = _validate_doctor_fields(
            i,
            doctor_name[i],
            doctor_specialization[i] if i < len(doctor_specialization) else "",
            doctor_qualification[i] if i < len(doctor_qualification) else "",
            doctor_years_experience[i] if i < len(doctor_years_experience) else "",
            doctor_working_days[i] if i < len(doctor_working_days) else "",
            doctor_working_hours[i] if i < len(doctor_working_hours) else "",
            doctor_slot_duration_minutes[i] if i < len(doctor_slot_duration_minutes) else "",
            _at(doctor_breaks, i), _at(doctor_max_bookings_per_slot, i), _at(doctor_daily_booking_limit, i),
            _at(doctor_online_quota, i), _at(doctor_walkin_quota, i),
            _at(doctor_followup_duration_minutes, i), _at(doctor_effective_from, i),
        )
        errors.extend(doc_errors)
        warnings.extend(doc_warnings)
        if doctor is not None:
            departments[dept_idx]["doctors"].append(doctor)

    for i, dept in enumerate(departments):
        if dept["doctors"] and not dept["name"]:
            errors.append(f"Department #{i + 1} has doctors listed but no department name.")

    departments = [d for d in departments if d["name"] and d["doctors"]]
    return departments, errors, warnings


def _build_faq_topics(topic_label: list[str], topic_answer: list[str]) -> tuple[list[dict], list[str]]:
    """Reconstructs topic/answer pairs from the wizard's repeatable topic-card
    fields (Step 8, faq-flow tenants — Section 14.3), mirroring
    _build_departments()'s "skip a card that's entirely empty, error on one
    that's half-filled" shape. Positional pairing (topic_label[i] with
    topic_answer[i]) matches DOM submit order, same as the doctor-card arrays."""
    errors: list[str] = []
    topics: list[dict] = []
    count = max(len(topic_label), len(topic_answer))
    for i in range(count):
        label = (topic_label[i] if i < len(topic_label) else "").strip()
        answer = (topic_answer[i] if i < len(topic_answer) else "").strip()
        if not label and not answer:
            continue  # an untouched "+ Add topic" card -- not an error, just skipped
        if not label:
            errors.append(f"Topic #{i + 1}: label is required (it has an answer but no label).")
            continue
        if not answer:
            errors.append(f'Topic #{i + 1} ("{label}"): answer text is required.')
            continue
        topics.append({"topic_label": label, "answer_text": answer})
    return topics, errors


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


# --- HTML/CSS/JS --- (shared _STYLE now lives in admin/theme.py)


# Section 14.6: reordered so the tier (data connection) choice comes first,
# before any Meta setup steps -- matches the reference design's own Step 0
# ("Choose your hospital setup") preceding "1. Connect your Meta account".
# Index 0 in this list is genuinely rendered as "Step 0" (not 1-indexed) --
# see the wizard JS's rail-building loop below, which starts at 0 to match.
_RAIL_TITLES = [
    "Data Connection",
    "Meta Business Account",
    "WhatsApp on Meta App",
    "Verify Business & Number",
    "Permanent Access Token",
    "Phone Number & App Secret",
    "Patient Experience",
    "Hospital Details",
    "Review & Submit",
]

_WIZARD_TEMPLATE = """<!doctype html>
<html>
<head>
<title>Onboard a new hospital</title>
""" + _STYLE + """
</head>
<body>
<div class="shell">

  <div class="brand">
    <div class="brand-mark">H</div>
    <span class="brand-name">Hospital Onboarding</span>
    <span class="brand-sub">— guided setup wizard</span>
  </div>

  <nav class="rail" id="rail"></nav>
  <main class="main">
    <div id="error-banner"></div>
    <form id="wizard-form" method="post" action="/admin/onboard-hospital">

      <section class="step-panel" data-step="0">
        <p class="eyebrow">Step 0 of 9</p>
        <h2>Choose your hospital setup</h2>
        <p class="step-desc">Does a system you already use manage appointments/doctor scheduling today? This decides how the rest of this wizard is set up, so it comes first.</p>
        <div class="guide-box">
          <span class="guide-num">?</span>
          <div class="guide-text">
            <p>Most hospitals should pick option (a) — it means WhatsApp booking works immediately with no extra
            setup. Only pick (b) or (c) if you already have a separate system where doctors' schedules live today,
            and you need it to stay the single source of truth.</p>
          </div>
        </div>
        <div class="tier-grid">
          <div class="tier-card" data-tier="tier1">
            <span class="tier-badge">Recommended default</span>
            <h3>Tier 1 — Use this platform</h3>
            <p>No existing system, or WhatsApp will be the only booking channel. No further setup needed.</p>
            <p class="tier-consequence">Ready immediately, no IT involvement needed.</p>
          </div>
          <div class="tier-card" data-tier="tier2">
            <h3>Tier 2 — Connect existing API</h3>
            <p>An existing system already manages scheduling, and it has an API we can call.</p>
            <p class="tier-consequence">Requires your existing system's API details — we'll build the connection once you provide them.</p>
          </div>
          <div class="tier-card" data-tier="tier3">
            <h3>Tier 3 — Direct database</h3>
            <p>An existing system manages scheduling, but only direct database access is possible.</p>
            <p class="tier-consequence">Requires your IT team to set up secure access — our team will follow up with you directly.</p>
          </div>
        </div>
        <input type="hidden" id="f-data_tier" name="data_tier" value="tier1">

        <div class="tier2-fields" id="tier2-fields">
          <label for="f-api_base_url">API base URL</label>
          <input type="text" id="f-api_base_url" name="api_base_url">
          <label for="f-api_key">API key</label>
          <input type="text" id="f-api_key" name="api_key">
        </div>
        <div class="tier3-note" id="tier3-note">
          Direct database connection is not self-serve — it requires a secure/VPN-reachable connection and a
          scoped-down database user, set up as a manually-assisted engagement. No fields to fill in here;
          we'll be in touch to arrange it after you submit.
        </div>

        <div class="nav-buttons">
          <span></span>
          <button type="button" class="next-btn" data-step="0">Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="1">
        <p class="eyebrow">Step 1 of 9</p>
        <h2>Create a Meta Business Account</h2>
        <p class="step-desc">This is the account Meta uses to identify the hospital as a real business before it can send WhatsApp messages.</p>
        <div class="guide-box">
          <span class="guide-num">1</span>
          <div class="guide-text">
            <ol>
              <li>Click <strong>Create Account</strong> (top right).</li>
              <li>Enter your hospital's name, your own name, and your work email.</li>
              <li>Check your email inbox and click the verification link Meta sends you.</li>
              <li>Come back to this wizard and check the box below once done.</li>
            </ol>
            <a class="ext-link" href="https://business.facebook.com" target="_blank" rel="noopener">Open business.facebook.com ↗</a>
          </div>
        </div>
        <label class="checkbox-row"><input type="checkbox" class="step-done-checkbox" data-step="1"> I've done this</label>
        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="1">Back</button>
          <button type="button" class="next-btn" data-step="1" disabled>Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="2">
        <p class="eyebrow">Step 2 of 9</p>
        <h2>Set up WhatsApp on a Meta app</h2>
        <p class="step-desc">The app is where the hospital's WhatsApp number and messaging permissions actually live.</p>
        <div class="guide-box">
          <span class="guide-num">1</span>
          <div class="guide-text">
            <ol>
              <li>Log in with the <strong>same</strong> account you used in Step 1.</li>
              <li>Click <strong>My Apps</strong> (top right) → <strong>Create App</strong>.</li>
              <li>Choose <strong>Business</strong> as the app type → give it any name (e.g. "[Hospital Name] WhatsApp") → enter a contact email → <strong>Create App</strong>.</li>
              <li>On your new app's dashboard, scroll to <strong>Add Products to Your App</strong> → find <strong>WhatsApp</strong> → click <strong>Set Up</strong>.</li>
              <li>This takes you to the <strong>API Setup</strong> page — you'll come back here in Step 5 to copy two values.</li>
            </ol>
            <a class="ext-link" href="https://developers.facebook.com" target="_blank" rel="noopener">Open developers.facebook.com ↗</a>
          </div>
        </div>
        <label class="checkbox-row"><input type="checkbox" class="step-done-checkbox" data-step="2"> I've done this</label>
        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="2">Back</button>
          <button type="button" class="next-btn" data-step="2" disabled>Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="3">
        <p class="eyebrow">Step 3 of 9</p>
        <h2>Verify business, register number, add payment</h2>
        <p class="step-desc">Genuine per-hospital steps on Meta's side — no wizard can skip these.</p>
        <div class="guide-box">
          <span class="guide-num">1</span>
          <div class="guide-text">
            <ol>
              <li>Go to <strong>business.facebook.com/settings</strong> → left sidebar → <strong>Security Center</strong> → <strong>Start Verification</strong>.</li>
              <li>Follow Meta's prompts — you'll need your hospital's legal business name, address, and a document like a business registration certificate or tax ID.</li>
              <li>This can take Meta a few hours to a few days to review — you can continue to later wizard steps while waiting, but your number won't be able to message real patients until this completes.</li>
              <li>Once verified, go back to your app's <strong>WhatsApp → API Setup</strong> page → find <strong>Step 2: Add a phone number</strong> → register your hospital's real WhatsApp number (not a personal number already using regular WhatsApp) and verify it via the code Meta texts you.</li>
              <li>Still on that page, find <strong>Add payment method</strong> → add a card. This is required before sending messages, but you are only charged for messages actually sent later — adding the card itself is free.</li>
            </ol>
          </div>
        </div>
        <label class="checkbox-row"><input type="checkbox" class="step-done-checkbox" data-step="3"> I've done this</label>
        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="3">Back</button>
          <button type="button" class="next-btn" data-step="3" disabled>Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="4">
        <p class="eyebrow">Step 4 of 9</p>
        <h2>Generate a permanent access token</h2>
        <p class="step-desc">This avoids the default token expiring every 24 hours.</p>
        <div class="guide-box">
          <span class="guide-num">1</span>
          <div class="guide-text">
            <ol>
              <li>Go to <strong>business.facebook.com/settings</strong> → <strong>Users</strong> → <strong>System Users</strong> → <strong>Add</strong>.</li>
              <li>Give it a name (e.g. "[Hospital Name] Bot") and set its role to <strong>Admin</strong>.</li>
              <li>Click <strong>Assign Assets</strong> → <strong>Apps</strong> tab → select the app you created in Step 2 → give it <strong>Full Control</strong>.</li>
              <li>Click <strong>Generate New Token</strong> → select that same app → under permissions, check <strong>whatsapp_business_messaging</strong> and <strong>whatsapp_business_management</strong> → set expiration to <strong>Never</strong> → <strong>Generate Token</strong>.</li>
              <li><strong>Copy the token immediately and paste it below</strong> — Meta only shows it once; if you lose it, you'll need to generate a new one.</li>
            </ol>
          </div>
        </div>
        <label for="f-access_token">Access token</label>
        <input type="text" id="f-access_token" name="access_token" placeholder="EAAxxxxxxxxxxxxxxxxxxxxxxx">
        <p class="field-hint">You'll find this on the System User's "Generate token" screen.</p>
        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="4">Back</button>
          <button type="button" class="next-btn" data-step="4">Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="5">
        <p class="eyebrow">Step 5 of 9</p>
        <h2>Paste your remaining credentials</h2>
        <p class="step-desc">Both of these come from the app created in Step 2.</p>
        <div class="guide-box">
          <span class="guide-num">1</span>
          <div class="guide-text">
            <ol>
              <li>Go back to your app's <strong>WhatsApp → API Setup</strong> page (from Step 2).</li>
              <li>Copy the <strong>Phone Number ID</strong> shown there and paste it below.</li>
              <li>Go to your app's <strong>Settings → Basic</strong> → click <strong>Show</strong> next to <strong>App Secret</strong> → copy and paste it below.</li>
            </ol>
          </div>
        </div>
        <label for="f-whatsapp_phone_number_id">WhatsApp phone_number_id</label>
        <input type="text" id="f-whatsapp_phone_number_id" name="whatsapp_phone_number_id" required>
        <label for="f-app_secret">App secret</label>
        <input type="text" id="f-app_secret" name="app_secret">
        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="5">Back</button>
          <button type="button" class="next-btn" data-step="5">Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="6">
        <p class="eyebrow">Step 6 of 9</p>
        <h2>What should patients be able to do on WhatsApp?</h2>
        <p class="step-desc">Select every capability this hospital wants to offer — patients only ever see the ones you turn on here. You can change this later.</p>
        <div class="tier-grid feature-grid" style="grid-template-columns: repeat(3, 1fr);">
          <label class="tier-card feature-card">
            <input type="checkbox" class="feature-checkbox" name="enabled_features" value="booking" checked>
            <h3>Book Appointment</h3>
            <p>Patients pick a department, doctor, and time slot.</p>
          </label>
          <label class="tier-card feature-card">
            <input type="checkbox" class="feature-checkbox" name="enabled_features" value="reschedule" checked>
            <h3>Reschedule Appointment</h3>
            <p>Move an existing booking to a new time.</p>
          </label>
          <label class="tier-card feature-card">
            <input type="checkbox" class="feature-checkbox" name="enabled_features" value="cancel" checked>
            <h3>Cancel Appointment</h3>
            <p>Cancel an existing booking.</p>
          </label>
          <label class="tier-card feature-card">
            <input type="checkbox" class="feature-checkbox" name="enabled_features" value="view_appointments" checked>
            <h3>View My Appointments</h3>
            <p>See a list of upcoming bookings.</p>
          </label>
          <label class="tier-card feature-card">
            <input type="checkbox" class="feature-checkbox" name="enabled_features" value="hospital_info" checked>
            <h3>Hospital Information</h3>
            <p>Hours, location, and general info.</p>
          </label>
          <label class="tier-card feature-card">
            <input type="checkbox" class="feature-checkbox" name="enabled_features" value="reception_handoff" checked>
            <h3>Talk to Reception</h3>
            <p>Hand off to a human -- queues into the staff portal's Messages inbox.</p>
          </label>
          <label class="tier-card feature-card">
            <input type="checkbox" class="feature-checkbox" name="enabled_features" value="faq">
            <h3>FAQ / Information Bot</h3>
            <p>Patients pick a topic (hours, pricing...) and get an instant configured answer.</p>
          </label>
        </div>

        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="6">Back</button>
          <button type="button" class="next-btn" data-step="6">Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="7">
        <p class="eyebrow">Step 7 of 9</p>
        <h2 id="hospital-details-heading">Add departments &amp; doctors</h2>
        <p class="step-desc" id="hospital-details-desc">This drives real slot generation — patients only see times a doctor is actually working.</p>
        <label for="f-name">Hospital name</label>
        <input type="text" id="f-name" name="name" required>
        <label for="f-welcome_message_text">Welcome message text</label>
        <textarea id="f-welcome_message_text" name="welcome_message_text" rows="2"
                  placeholder="Hi! Welcome to [Hospital Name]. How can we help you today?"></textarea>

        <div id="booking-fields">
          <div class="field-row">
            <div>
              <label for="f-reminder_offsets_hours">Reminder offsets (comma-separated hours)</label>
              <input type="text" id="f-reminder_offsets_hours" name="reminder_offsets_hours" placeholder="24,1" value="24">
              <p class="field-hint">Enter hours before the appointment, separated by commas — e.g. 24,1 sends a reminder one day before and one hour before.</p>
            </div>
            <div>
              <label for="f-reminder_template_name">Reminder template name</label>
              <input type="text" id="f-reminder_template_name" name="reminder_template_name">
              <p class="field-hint">This must match a message template you've submitted for approval in Meta's WhatsApp Manager — we'll help you with the exact wording to submit.</p>
            </div>
          </div>

          <label for="f-portal_password">Bookings portal password (optional)</label>
          <input type="password" id="f-portal_password" name="portal_password" placeholder="Leave blank to set this later">
          <p class="field-hint">Your own staff can use this to log into a simple dashboard at /portal/login and see every appointment booked through WhatsApp (Tier 1 only). You can set or change it anytime after onboarding too.</p>

          <label style="margin-top: 28px;">Departments &amp; doctors</label>
          <div id="departments-container"></div>
          <button type="button" class="add-doctor" id="add-department-btn" style="margin-top:14px;">+ Add department</button>
        </div>

        <div id="faq-fields" style="display:none;">
          <label style="margin-top: 28px;">Topics &amp; answers</label>
          <p class="field-hint">Each topic becomes an option patients tap on WhatsApp — e.g. "Hours," "Location," "Pricing." Keep answers short and clear.</p>
          <div id="topics-container"></div>
          <button type="button" class="add-doctor" id="add-topic-btn" style="margin-top:14px;">+ Add topic</button>
        </div>

        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="7">Back</button>
          <button type="button" class="next-btn" data-step="7">Next</button>
        </div>
      </section>

      <section class="step-panel" data-step="8">
        <p class="eyebrow">Step 8 of 9</p>
        <h2>Review &amp; go live</h2>
        <p class="step-desc">One last look before this hospital is created and immediately bookable.</p>
        <div class="review-block" id="review-block"></div>
        <p class="go-live-note">Once you submit, your hospital will be live and bookable through WhatsApp within a few minutes.</p>
        <label for="f-admin_secret" style="margin-top:24px;">Admin secret</label>
        <input type="password" id="f-admin_secret" name="admin_secret" required>
        <div class="nav-buttons">
          <button type="button" class="back-btn" data-step="8">Back</button>
          <button type="submit" id="submit-btn">Create hospital</button>
        </div>
      </section>

    </form>
  </main>
</div>

<template id="doctor-card-template">
  <div class="doctor-card">
    <div class="doctor-card-header">
      <strong>Doctor</strong>
      <button type="button" class="remove-link remove-doctor-btn">Remove</button>
    </div>
    <input type="hidden" class="doctor-department-index" name="doctor_department_index" value="">
    <div class="field-row">
      <div><label>Name</label><input type="text" class="doctor-name" name="doctor_name"></div>
      <div><label>Specialization</label><input type="text" class="doctor-specialization" name="doctor_specialization"></div>
    </div>
    <div class="field-row">
      <div><label>Qualification</label><input type="text" class="doctor-qualification" name="doctor_qualification"></div>
      <div><label>Years experience</label><input type="number" min="0" class="doctor-years" name="doctor_years_experience"></div>
    </div>
    <label>Working days</label>
    <button type="button" class="select-all-days-btn small">Select all weekdays</button>
    <button type="button" class="copy-days-btn small">Copy to other days</button>
    <div class="days-row"></div>
    <div class="copy-days-row" style="display:none;"></div>
    <input type="hidden" class="doctor-working-days" name="doctor_working_days" value="">
    <div class="field-row">
      <div>
        <label>Working hours</label>
        <div class="shifts-row"></div>
        <button type="button" class="add-doctor add-shift-btn small">+ Add another shift</button>
        <input type="hidden" class="doctor-hours" name="doctor_working_hours" value="">
        <p class="field-hint">Pick start/end times — most doctors only need one shift. Add another row for a split shift (e.g. morning + evening). Applies to every working day selected above.</p>
      </div>
      <div>
        <label>Slot duration (minutes)</label>
        <input type="number" min="1" class="doctor-duration" name="doctor_slot_duration_minutes">
        <p class="field-hint">This is how long each appointment lasts — e.g. 20 means patients can book a new slot every 20 minutes.</p>
      </div>
    </div>
    <div class="field-row">
      <div>
        <label>Breaks (optional)</label>
        <div class="breaks-row"></div>
        <button type="button" class="add-doctor add-break-btn small">+ Add a break</button>
        <input type="hidden" class="doctor-breaks" name="doctor_breaks" value="">
        <p class="field-hint">e.g. a lunch break — excluded from bookable slots within whichever shift it falls in, every working day.</p>
      </div>
      <div>
        <label>Follow-up duration (minutes, optional)</label>
        <input type="number" min="1" class="doctor-followup-duration" name="doctor_followup_duration_minutes">
        <p class="field-hint">If set, a separate (usually shorter) slot length offered for follow-up visits.</p>
      </div>
    </div>
    <div class="field-row">
      <div>
        <label>Bookings per slot</label>
        <input type="number" min="1" class="doctor-max-bookings" name="doctor_max_bookings_per_slot" value="1">
        <p class="field-hint">How many patients can book the exact same slot time. 1 = today's normal behavior.</p>
      </div>
      <div>
        <label>Daily booking limit (optional)</label>
        <input type="number" min="0" class="doctor-daily-limit" name="doctor_daily_booking_limit">
        <p class="field-hint">Caps total bookings per day for this doctor, regardless of how many slots exist.</p>
      </div>
    </div>
    <div class="field-row">
      <div>
        <label>Online quota (optional)</label>
        <input type="number" min="0" class="doctor-online-quota" name="doctor_online_quota">
      </div>
      <div>
        <label>Walk-in quota (optional)</label>
        <input type="number" min="0" class="doctor-walkin-quota" name="doctor_walkin_quota">
        <p class="field-hint">Reserved split of the daily limit between WhatsApp and front-desk bookings. Walk-in booking isn't built yet, so this doesn't affect availability until it is.</p>
      </div>
    </div>
    <div class="field-row">
      <div>
        <label>Schedule effective from (optional)</label>
        <input type="date" class="doctor-effective-from" name="doctor_effective_from">
        <p class="field-hint">Leave blank for "effective immediately." Setting a future date keeps this doctor's already-offered earlier slots untouched.</p>
      </div>
      <div></div>
    </div>
  </div>
</template>

<template id="shift-row-template">
  <div class="shift-row">
    <input type="time" class="shift-start">
    <span class="shift-sep">to</span>
    <input type="time" class="shift-end">
    <button type="button" class="remove-link remove-shift-btn">Remove</button>
  </div>
</template>

<template id="break-row-template">
  <div class="shift-row">
    <input type="time" class="break-start">
    <span class="shift-sep">to</span>
    <input type="time" class="break-end">
    <button type="button" class="remove-link remove-break-btn">Remove</button>
  </div>
</template>

<template id="department-card-template">
  <div class="dept-card">
    <div class="dept-card-header">
      <input type="text" class="department-name" name="department_name" placeholder="Department name">
      <button type="button" class="remove-link remove-department-btn">Remove department</button>
    </div>
    <div class="doctors-container"></div>
    <button type="button" class="add-doctor add-doctor-btn" style="margin-top:14px;">+ Add doctor</button>
  </div>
</template>

<template id="topic-card-template">
  <div class="dept-card topic-card">
    <div class="dept-card-header">
      <input type="text" class="topic-label" name="topic_label" placeholder="Topic (e.g. Hours)">
      <button type="button" class="remove-link remove-topic-btn">Remove topic</button>
    </div>
    <label>Answer</label>
    <textarea class="topic-answer" name="topic_answer" rows="2" placeholder="e.g. We're open Mon-Sat, 9:00 AM - 6:00 PM."></textarea>
  </div>
</template>

<script>
window.__WIZARD_BOOTSTRAP__ = __BOOTSTRAP_JSON__;
window.__WIZARD_ERRORS__ = __ERRORS_JSON__;
</script>
<script>
(function () {
  var RAIL_TITLES = __RAIL_TITLES_JSON__;
  var WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  var totalSteps = RAIL_TITLES.length;
  // Section 14.6: Step 0 (tier choice) genuinely IS step zero, not a
  // 1-indexing quirk -- matches the reference design's own "0. Choose your
  // hospital setup" preceding "1. Connect your Meta account". Every step
  // number below is 0-indexed accordingly (0..totalSteps-1).
  var currentStep = 0;
  var maxUnlockedStep = 0;

  var rail = document.getElementById("rail");
  var railHtml = '<h1>Onboard a hospital</h1>';
  for (var i = 0; i < totalSteps; i++) {
    railHtml += '<div class="rail-step" data-step="' + i + '"><span class="dot">' + i + '</span><span>' + RAIL_TITLES[i] + '</span></div>';
  }
  rail.innerHTML = railHtml;

  function renderRail() {
    var items = rail.querySelectorAll(".rail-step");
    items.forEach(function (item) {
      var step = parseInt(item.getAttribute("data-step"), 10);
      item.classList.remove("active", "done", "clickable");
      if (step === currentStep) item.classList.add("active");
      if (step < maxUnlockedStep) item.classList.add("done", "clickable");
      if (step <= maxUnlockedStep) item.classList.add("clickable");
    });
  }

  function goToStep(step) {
    if (step > maxUnlockedStep) return;
    document.querySelectorAll(".step-panel").forEach(function (p) {
      p.classList.toggle("active", parseInt(p.getAttribute("data-step"), 10) === step);
    });
    currentStep = step;
    renderRail();
    window.scrollTo(0, 0);
    if (step === totalSteps - 1) renderReview();
  }

  rail.addEventListener("click", function (e) {
    var item = e.target.closest(".rail-step");
    if (!item) return;
    var step = parseInt(item.getAttribute("data-step"), 10);
    if (step <= maxUnlockedStep) goToStep(step);
  });

  // Every back-btn just goes to step-1 -- no more skip-a-step special-casing
  // now that the data-tier choice (the thing that used to be conditionally
  // skipped) is Step 0, always shown, never conditional (Section 14.6).
  document.querySelectorAll(".back-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      goToStep(parseInt(btn.getAttribute("data-step"), 10) - 1);
    });
  });

  document.querySelectorAll(".step-done-checkbox").forEach(function (box) {
    box.addEventListener("change", function () {
      var step = box.getAttribute("data-step");
      var nextBtn = document.querySelector('.next-btn[data-step="' + step + '"]');
      nextBtn.disabled = !box.checked;
    });
  });

  function validateStep(step) {
    if (step === 0) {
      var tier = document.getElementById("f-data_tier").value;
      if (tier === "tier2") {
        var base = document.getElementById("f-api_base_url").value.trim();
        var key = document.getElementById("f-api_key").value.trim();
        if (!base || !key) { alert("API base URL and API key are both required for Tier 2."); return false; }
      }
    }
    if (step === 5) {
      var pid = document.getElementById("f-whatsapp_phone_number_id").value.trim();
      if (!pid) { alert("WhatsApp phone_number_id is required."); return false; }
    }
    if (step === 6) {
      var anyFeatureChecked = document.querySelectorAll(".feature-checkbox:checked").length > 0;
      if (!anyFeatureChecked) { alert("Select at least one capability for patients to use."); return false; }
    }
    if (step === 7) {
      var name = document.getElementById("f-name").value.trim();
      if (!name) { alert("Hospital name is required."); return false; }
      if (document.querySelector('.feature-checkbox[value="booking"]').checked) {
        recomputeDepartmentIndices();
        var doctorCount = document.querySelectorAll(".doctor-card").length;
        if (doctorCount === 0) { alert("Booking is enabled, so at least one department with at least one doctor is required."); return false; }
      }
      if (document.querySelector('.feature-checkbox[value="faq"]').checked) {
        var topicCount = 0;
        document.querySelectorAll(".topic-card").forEach(function (card) {
          var label = card.querySelector(".topic-label").value.trim();
          var answer = card.querySelector(".topic-answer").value.trim();
          if (label && answer) topicCount++;
        });
        if (topicCount === 0) { alert("FAQ / Information Bot is enabled, so at least one topic with a label and an answer is required."); return false; }
      }
    }
    return true;
  }

  document.querySelectorAll(".next-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var step = parseInt(btn.getAttribute("data-step"), 10);
      if (!validateStep(step)) return;
      if (step + 1 > maxUnlockedStep) maxUnlockedStep = step + 1;
      goToStep(step + 1);
    });
  });

  // --- Tier cards (Step 0) ---
  document.querySelectorAll(".tier-card[data-tier]").forEach(function (card) {
    card.addEventListener("click", function () {
      document.querySelectorAll(".tier-card[data-tier]").forEach(function (c) { c.classList.remove("selected"); });
      card.classList.add("selected");
      var tier = card.getAttribute("data-tier");
      document.getElementById("f-data_tier").value = tier;
      document.getElementById("tier2-fields").style.display = tier === "tier2" ? "block" : "none";
      document.getElementById("tier3-note").style.display = tier === "tier3" ? "block" : "none";
    });
  });

  // --- Feature toggles (Step 6, Section 14.6) ---
  // Multi-select (unlike Step 0's tier cards above, which are exclusive) --
  // a hospital enables any combination of capabilities. Toggling "booking"
  // or "faq" also shows/hides the matching section of Step 7 (Hospital
  // Details), since both can be on at once now.
  function updateHospitalDetailsVisibility() {
    var bookingEnabled = document.querySelector('.feature-checkbox[value="booking"]').checked;
    var faqEnabled = document.querySelector('.feature-checkbox[value="faq"]').checked;
    document.getElementById("booking-fields").style.display = bookingEnabled ? "block" : "none";
    document.getElementById("faq-fields").style.display = faqEnabled ? "block" : "none";
    var parts = [];
    if (bookingEnabled) parts.push("departments & doctors");
    if (faqEnabled) parts.push("topics & answers");
    document.getElementById("hospital-details-heading").textContent = parts.length ? "Add " + parts.join(" and ") : "Hospital details";
    document.getElementById("hospital-details-desc").textContent = bookingEnabled
      ? "This drives real slot generation — patients only see times a doctor is actually working."
      : (faqEnabled ? "Each topic becomes a tappable option — patients get an instant answer, no scheduling involved."
                    : "Basic details for this hospital.");
  }
  document.querySelectorAll(".feature-checkbox").forEach(function (box) {
    box.closest(".feature-card").classList.toggle("selected", box.checked);
    box.addEventListener("change", function () {
      box.closest(".feature-card").classList.toggle("selected", box.checked);
      updateHospitalDetailsVisibility();
    });
  });
  updateHospitalDetailsVisibility();

  // --- Department / doctor cards (Step 7) ---
  var deptContainer = document.getElementById("departments-container");
  var deptTemplate = document.getElementById("department-card-template");
  var doctorTemplate = document.getElementById("doctor-card-template");
  var shiftTemplate = document.getElementById("shift-row-template");

  // Native <input type="time"> always yields zero-padded 24h "HH:MM" (browser-
  // enforced, no way to type "10-12:00" or "9:00" into it) -- replaces the old
  // free-text "comma-separated HH:MM-HH:MM ranges" field, which was the most
  // common submission error (missing leading zero, wrong separator, etc.).
  // The hidden .doctor-hours input is recomputed from these on every change,
  // so the backend's existing _TIME_RANGE_RE validation/format is untouched.
  function addShiftRow(shiftsRow, hiddenHours, start, end) {
    var node = shiftTemplate.content.cloneNode(true);
    var row = node.querySelector(".shift-row");
    row.querySelector(".shift-start").value = start || "";
    row.querySelector(".shift-end").value = end || "";

    function recompute() {
      var ranges = [];
      shiftsRow.querySelectorAll(".shift-row").forEach(function (r) {
        var s = r.querySelector(".shift-start").value;
        var e = r.querySelector(".shift-end").value;
        if (s && e) ranges.push(s + "-" + e);
      });
      hiddenHours.value = ranges.join(",");
    }

    row.querySelector(".shift-start").addEventListener("change", recompute);
    row.querySelector(".shift-end").addEventListener("change", recompute);
    row.querySelector(".remove-shift-btn").addEventListener("click", function () {
      row.remove();
      recompute();
    });
    shiftsRow.appendChild(row);
    recompute();
  }

  // Same pattern as addShiftRow() above, for the (optional) breaks list --
  // breaks-row-template is a plain time-range pair like a shift row, just
  // feeding the .doctor-breaks hidden field instead of .doctor-hours.
  var breakTemplate = document.getElementById("break-row-template");
  function addBreakRow(breaksRow, hiddenBreaks, start, end) {
    var node = breakTemplate.content.cloneNode(true);
    var row = node.querySelector(".shift-row");
    row.querySelector(".break-start").value = start || "";
    row.querySelector(".break-end").value = end || "";

    function recompute() {
      var ranges = [];
      breaksRow.querySelectorAll(".shift-row").forEach(function (r) {
        var s = r.querySelector(".break-start").value;
        var e = r.querySelector(".break-end").value;
        if (s && e) ranges.push(s + "-" + e);
      });
      hiddenBreaks.value = ranges.join(",");
    }

    row.querySelector(".break-start").addEventListener("change", recompute);
    row.querySelector(".break-end").addEventListener("change", recompute);
    row.querySelector(".remove-break-btn").addEventListener("click", function () {
      row.remove();
      recompute();
    });
    breaksRow.appendChild(row);
    recompute();
  }

  function addDoctorCard(deptCard, data) {
    data = data || {};
    var doctorsContainer = deptCard.querySelector(".doctors-container");
    var node = doctorTemplate.content.cloneNode(true);
    var card = node.querySelector(".doctor-card");

    card.querySelector(".doctor-name").value = data.name || "";
    card.querySelector(".doctor-specialization").value = data.specialization || "";
    card.querySelector(".doctor-qualification").value = data.qualification || "";
    card.querySelector(".doctor-years").value = data.years_experience || "";
    card.querySelector(".doctor-duration").value = data.slot_duration_minutes || "";
    card.querySelector(".doctor-max-bookings").value = data.max_bookings_per_slot || 1;
    card.querySelector(".doctor-daily-limit").value = data.daily_booking_limit != null ? data.daily_booking_limit : "";
    card.querySelector(".doctor-online-quota").value = data.online_quota != null ? data.online_quota : "";
    card.querySelector(".doctor-walkin-quota").value = data.walkin_quota != null ? data.walkin_quota : "";
    card.querySelector(".doctor-followup-duration").value = data.followup_duration_minutes || "";
    card.querySelector(".doctor-effective-from").value = data.effective_from || "";

    var shiftsRow = card.querySelector(".shifts-row");
    var hiddenHours = card.querySelector(".doctor-hours");
    var existingHours = data.working_hours || [];
    if (existingHours.length) {
      existingHours.forEach(function (range) {
        var parts = range.split("-");
        addShiftRow(shiftsRow, hiddenHours, parts[0], parts[1]);
      });
    } else {
      addShiftRow(shiftsRow, hiddenHours, "", "");
    }
    card.querySelector(".add-shift-btn").addEventListener("click", function () {
      addShiftRow(shiftsRow, hiddenHours, "", "");
    });

    var breaksRow = card.querySelector(".breaks-row");
    var hiddenBreaks = card.querySelector(".doctor-breaks");
    (data.breaks || []).forEach(function (range) {
      var parts = range.split("-");
      addBreakRow(breaksRow, hiddenBreaks, parts[0], parts[1]);
    });
    card.querySelector(".add-break-btn").addEventListener("click", function () {
      addBreakRow(breaksRow, hiddenBreaks, "", "");
    });

    var selectedDays = data.working_days || [];
    var daysRow = card.querySelector(".days-row");
    var hiddenDays = card.querySelector(".doctor-working-days");
    WEEKDAYS.forEach(function (day) {
      var toggle = document.createElement("div");
      toggle.className = "day-toggle" + (selectedDays.indexOf(day) !== -1 ? " on" : "");
      toggle.textContent = day;
      toggle.addEventListener("click", function () {
        toggle.classList.toggle("on");
        var on = [];
        daysRow.querySelectorAll(".day-toggle.on").forEach(function (t) { on.push(t.textContent); });
        hiddenDays.value = on.join(",");
      });
      daysRow.appendChild(toggle);
    });
    hiddenDays.value = selectedDays.join(",");

    // "Select all weekdays" quick-toggle: simulates a click on each not-yet-on
    // Mon-Fri toggle, reusing that toggle's own click handler above (so the
    // hidden field recompute logic isn't duplicated) -- leaves Sat/Sun as-is.
    card.querySelector(".select-all-days-btn").addEventListener("click", function () {
      daysRow.querySelectorAll(".day-toggle").forEach(function (toggle) {
        var isWeekday = ["Sat", "Sun"].indexOf(toggle.textContent) === -1;
        if (isWeekday && !toggle.classList.contains("on")) toggle.click();
      });
    });

    // "Copy to other days" (Section 14.7): this doctor's shifts/breaks/slot
    // duration already apply uniformly to every checked working day (there's
    // no separate per-day configuration to copy FROM) -- so "copying" them to
    // more days is exactly "select more days," reusing each day-toggle's own
    // click handler above rather than duplicating the hidden-field recompute
    // logic. A form-population convenience only, per Section 14.7's own
    // scope note -- the backend just sees a normal, longer doctor_working_days
    // list either way.
    var copyDaysRow = card.querySelector(".copy-days-row");
    card.querySelector(".copy-days-btn").addEventListener("click", function () {
      var visible = copyDaysRow.style.display !== "none";
      if (visible) { copyDaysRow.style.display = "none"; return; }
      copyDaysRow.innerHTML = "";
      WEEKDAYS.forEach(function (day) {
        var label = document.createElement("label");
        label.className = "checkbox-row";
        var box = document.createElement("input");
        box.type = "checkbox";
        box.value = day;
        label.appendChild(box);
        label.appendChild(document.createTextNode(" " + day));
        copyDaysRow.appendChild(label);
      });
      var applyBtn = document.createElement("button");
      applyBtn.type = "button";
      applyBtn.className = "small";
      applyBtn.textContent = "Apply";
      applyBtn.addEventListener("click", function () {
        copyDaysRow.querySelectorAll("input:checked").forEach(function (box) {
          var toggle = Array.prototype.find.call(daysRow.querySelectorAll(".day-toggle"), function (t) {
            return t.textContent === box.value;
          });
          if (toggle && !toggle.classList.contains("on")) toggle.click();
        });
        copyDaysRow.style.display = "none";
      });
      copyDaysRow.appendChild(applyBtn);
      copyDaysRow.style.display = "block";
    });

    card.querySelector(".remove-doctor-btn").addEventListener("click", function () { card.remove(); });
    doctorsContainer.appendChild(card);
  }

  function addDepartmentCard(data) {
    data = data || {};
    var node = deptTemplate.content.cloneNode(true);
    var card = node.querySelector(".dept-card");
    card.querySelector(".department-name").value = data.name || "";
    card.querySelector(".remove-department-btn").addEventListener("click", function () { card.remove(); });
    card.querySelector(".add-doctor-btn").addEventListener("click", function () { addDoctorCard(card); });
    deptContainer.appendChild(card);
    (data.doctors || []).forEach(function (doc) { addDoctorCard(card, doc); });
  }

  document.getElementById("add-department-btn").addEventListener("click", function () { addDepartmentCard(); });

  function recomputeDepartmentIndices() {
    var deptCards = deptContainer.querySelectorAll(".dept-card");
    deptCards.forEach(function (deptCard, index) {
      deptCard.querySelectorAll(".doctor-department-index").forEach(function (input) {
        input.value = index;
      });
    });
  }

  // --- FAQ topic cards (Step 8, faq tenants only) ---
  var topicContainer = document.getElementById("topics-container");
  var topicTemplate = document.getElementById("topic-card-template");

  function addTopicCard(data) {
    data = data || {};
    var node = topicTemplate.content.cloneNode(true);
    var card = node.querySelector(".topic-card");
    card.querySelector(".topic-label").value = data.topic_label || "";
    card.querySelector(".topic-answer").value = data.answer_text || "";
    card.querySelector(".remove-topic-btn").addEventListener("click", function () { card.remove(); });
    topicContainer.appendChild(card);
  }

  document.getElementById("add-topic-btn").addEventListener("click", function () { addTopicCard(); });

  // --- Review (Step 9) ---
  // Masks all but the last 4 characters of a credential -- used for the
  // access token and app secret specifically (SPEC Section 12.1 Step 8);
  // everything else on the review screen is shown in full.
  function maskSecret(value) {
    if (!value) return "(not set)";
    if (value.length <= 4) return "••••";
    return "••••••••" + value.slice(-4);
  }

  function reviewSection(title, gotoStep, rows) {
    var html = '<div class="review-section"><div class="review-section-header">';
    html += "<h4>" + escapeHtml(title) + '</h4><a class="edit-link" data-goto="' + gotoStep + '">Edit</a></div>';
    html += "<dl>" + rows + "</dl></div>";
    return html;
  }

  var FEATURE_LABELS = {
    booking: "Book Appointment", reschedule: "Reschedule Appointment", cancel: "Cancel Appointment",
    view_appointments: "View My Appointments", hospital_info: "Hospital Information",
    reception_handoff: "Talk to Reception", faq: "FAQ / Information Bot",
  };

  function renderReview() {
    recomputeDepartmentIndices();
    var get = function (id) { return document.getElementById(id).value; };
    var tierLabels = {tier1: "Tier 1 — this platform", tier2: "Tier 2 — external API", tier3: "Tier 3 — direct database"};
    var bookingEnabled = document.querySelector('.feature-checkbox[value="booking"]').checked;
    var faqEnabled = document.querySelector('.feature-checkbox[value="faq"]').checked;

    var html = "";

    var tier = get("f-data_tier");
    var tierRows = "<dt>Data connection</dt><dd>" + escapeHtml(tierLabels[tier]) + "</dd>";
    if (tier === "tier2") {
      tierRows += "<dt>API base URL</dt><dd>" + escapeHtml(get("f-api_base_url")) + "</dd>";
      tierRows += "<dt>API key</dt><dd>" + escapeHtml(get("f-api_key")) + "</dd>";
    }
    html += reviewSection("Data connection (Step 0)", 0, tierRows);

    html += reviewSection("Access token (Step 4)", 4,
      "<dt>Access token</dt><dd>" + escapeHtml(maskSecret(get("f-access_token"))) + "</dd>");

    html += reviewSection("WhatsApp connection (Step 5)", 5,
      "<dt>Phone number ID</dt><dd>" + escapeHtml(get("f-whatsapp_phone_number_id")) + "</dd>" +
      "<dt>App secret</dt><dd>" + escapeHtml(maskSecret(get("f-app_secret"))) + "</dd>");

    var selectedFeatures = Array.prototype.map.call(
      document.querySelectorAll(".feature-checkbox:checked"),
      function (box) { return FEATURE_LABELS[box.value] || box.value; }
    );
    html += reviewSection("Patient experience (Step 6)", 6,
      "<dt>Enabled for patients</dt><dd>" + (selectedFeatures.length
        ? "<ul style='margin:0.3rem 0 0;padding-left:1.1rem;'>" + selectedFeatures.map(function (f) { return "<li>" + escapeHtml(f) + "</li>"; }).join("") + "</ul>"
        : "(none selected yet)") + "</dd>");

    var hospitalRows = "<dt>Hospital name</dt><dd>" + escapeHtml(get("f-name")) + "</dd>";
    hospitalRows += "<dt>Welcome message</dt><dd>" + escapeHtml(get("f-welcome_message_text") || "(not set)") + "</dd>";

    if (bookingEnabled) {
      hospitalRows += "<dt>Reminder offsets (hours)</dt><dd>" + escapeHtml(get("f-reminder_offsets_hours")) + "</dd>";
      hospitalRows += "<dt>Reminder template name</dt><dd>" + escapeHtml(get("f-reminder_template_name") || "(not set)") + "</dd>";
      hospitalRows += "<dt>Bookings portal password</dt><dd>" + (get("f-portal_password") ? "Set" : "Not set — can add later") + "</dd>";
      hospitalRows += "<dt>Departments &amp; doctors</dt><dd>";
      // Skips cards with no name AND no doctors -- an operator who clicked
      // "+ Add department" but didn't fill it in yet shouldn't see a
      // confusing "(unnamed department):" line; the backend's own
      // _build_departments() filters the same way, so this matches what will
      // actually get created.
      var deptCards = Array.prototype.filter.call(deptContainer.querySelectorAll(".dept-card"), function (deptCard) {
        return deptCard.querySelector(".department-name").value.trim() || deptCard.querySelectorAll(".doctor-card").length > 0;
      });
      if (deptCards.length === 0) {
        hospitalRows += "(none added yet)";
      } else {
        hospitalRows += "<ul style='margin:0.3rem 0 0;padding-left:1.1rem;'>";
        deptCards.forEach(function (deptCard) {
          var deptName = deptCard.querySelector(".department-name").value || "(unnamed department)";
          var doctorNames = [];
          deptCard.querySelectorAll(".doctor-card").forEach(function (dc) {
            doctorNames.push(dc.querySelector(".doctor-name").value || "(unnamed doctor)");
          });
          hospitalRows += "<li>" + escapeHtml(deptName) + ": " + escapeHtml(doctorNames.join(", ")) + "</li>";
        });
        hospitalRows += "</ul>";
      }
      hospitalRows += "</dd>";
    }

    if (faqEnabled) {
      hospitalRows += "<dt>Topics &amp; answers</dt><dd>";
      var topicCards = Array.prototype.filter.call(topicContainer.querySelectorAll(".topic-card"), function (tc) {
        return tc.querySelector(".topic-label").value.trim() || tc.querySelector(".topic-answer").value.trim();
      });
      if (topicCards.length === 0) {
        hospitalRows += "(none added yet)";
      } else {
        hospitalRows += "<ul style='margin:0.3rem 0 0;padding-left:1.1rem;'>";
        topicCards.forEach(function (tc) {
          var label = tc.querySelector(".topic-label").value || "(unnamed topic)";
          var answer = tc.querySelector(".topic-answer").value || "(no answer yet)";
          hospitalRows += "<li>" + escapeHtml(label) + ": " + escapeHtml(answer) + "</li>";
        });
        hospitalRows += "</ul>";
      }
      hospitalRows += "</dd>";
    }
    html += reviewSection("Hospital details (Step 7)", 7, hospitalRows);

    document.getElementById("review-block").innerHTML = html;
    document.querySelectorAll("#review-block .edit-link").forEach(function (link) {
      link.addEventListener("click", function () {
        goToStep(parseInt(link.getAttribute("data-goto"), 10));
      });
    });
  }

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s || "";
    return div.innerHTML;
  }

  document.getElementById("wizard-form").addEventListener("submit", function () {
    recomputeDepartmentIndices();
  });

  // --- Error banner + bootstrap repopulation (after a server-side validation error) ---
  var errors = window.__WIZARD_ERRORS__ || [];
  if (errors.length) {
    var banner = document.getElementById("error-banner");
    var itemsHtml = errors.map(function (e) { return "<li>" + escapeHtml(e) + "</li>"; }).join("");
    banner.innerHTML = '<div class="error-banner"><strong>Please fix the following:</strong><ul>' + itemsHtml + '</ul></div>';
  }

  var bootstrap = window.__WIZARD_BOOTSTRAP__ || {};
  var scalarFields = [
    "admin_secret", "name", "whatsapp_phone_number_id", "access_token", "app_secret",
    "welcome_message_text", "reminder_offsets_hours", "reminder_template_name",
    "portal_password", "api_base_url", "api_key",
  ];
  scalarFields.forEach(function (field) {
    var el = document.getElementById("f-" + field);
    if (el && bootstrap[field]) el.value = bootstrap[field];
  });
  (bootstrap.enabled_features || []).forEach(function (key) {
    var box = document.querySelector('.feature-checkbox[value="' + key + '"]');
    if (box) box.checked = true;
  });
  if (typeof updateHospitalDetailsVisibility === "function") updateHospitalDetailsVisibility();
  if (bootstrap.data_tier) {
    document.getElementById("f-data_tier").value = bootstrap.data_tier;
    var card = document.querySelector('.tier-card[data-tier="' + bootstrap.data_tier + '"]');
    if (card) card.click();
  }
  (bootstrap.departments || []).forEach(function (dept) { addDepartmentCard(dept); });
  (bootstrap.topics || []).forEach(function (topic) { addTopicCard(topic); });

  // Always land back on step 1 after an error -- the bootstrap data above
  // means nothing entered is lost, and the error banner (visible on every
  // step, outside the step panels) explains what to fix while stepping
  // through. maxUnlockedStep is opened all the way so the reviewer isn't
  // forced to re-click through every step to get back to where they were.
  // Deliberately NOT auto-adding an empty starting department card here --
  // one would still be present (named or not) when the operator reaches the
  // review step, showing up as a confusing "(unnamed department):" line;
  // "+ Add department" is one click away regardless.
  //
  // On a genuinely FRESH load (no errors), goToStep(1) must NOT run here --
  // maxUnlockedStep is still 0 at this point, so goToStep()'s own guard
  // (`if (step > maxUnlockedStep) return;`) silently no-ops it, leaving
  // every .step-panel at its default `display: none` with nothing ever
  // marked .active -- renderRail() still runs and cosmetically marks rail
  // item 0 as current (it just reads the untouched currentStep=0), which is
  // what made the page look like it loaded fine while the entire content
  // area stayed blank. Every fresh visitor hit this until now.
  if (errors.length) {
    maxUnlockedStep = totalSteps;
    renderRail();
    goToStep(1);
  } else {
    renderRail();
    goToStep(0);
  }
})();
</script>
</body>
</html>"""


def _wizard_html(
    errors: list[str] | None, values: dict, departments: list[dict], topics: list[dict] | None = None,
) -> str:
    bootstrap = dict(values)
    bootstrap["departments"] = departments
    bootstrap["topics"] = topics or []
    # Escape "</" so a value containing a literal "</script>" can't break out
    # of the inline <script> block it's embedded in.
    bootstrap_json = json.dumps(bootstrap).replace("</", "<\\/")
    errors_json = json.dumps(errors or []).replace("</", "<\\/")
    rail_titles_json = json.dumps(_RAIL_TITLES)

    page = _WIZARD_TEMPLATE
    page = page.replace("__BOOTSTRAP_JSON__", bootstrap_json)
    page = page.replace("__ERRORS_JSON__", errors_json)
    page = page.replace("__RAIL_TITLES_JSON__", rail_titles_json)
    return page


def _confirmation_html(
    hospital, departments: list[dict], secret: str = "", topics: list[dict] | None = None,
    warnings: list[str] | None = None,
) -> str:
    warning_html = ""
    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
        warning_html = f'<div class="warning-banner" style="margin-top: 20px;"><strong>Worth double-checking:</strong><ul>{items}</ul></div>'

    content_parts = []
    tier_note = {
        "tier1": "Using this platform's own database to manage appointments (Tier 1).",
        "tier2": "Connected to the hospital's existing API (Tier 2) — the base URL/key were "
                 "stored, but no connector logic runs against them yet (SPEC Section 12.6).",
        "tier3": "Flagged for direct database connection (Tier 3) — this is a manually-assisted "
                 "engagement, not self-serve; we'll be in touch to arrange secure access.",
    }[hospital.data_tier]
    content_parts.append(f"<p>{html.escape(tier_note)}</p>")
    if "booking" in hospital.enabled_features:
        dept_items = "".join(
            f"<li>{html.escape(d['name'])}: "
            f"{html.escape(', '.join(doc['name'] for doc in d['doctors']))}</li>"
            for d in departments
        )
        content_parts.append(f"<h3>Departments</h3>\n  <ul>{dept_items}</ul>")
    if "faq" in hospital.enabled_features:
        topic_items = "".join(
            f"<li>{html.escape(t['topic_label'])}: {html.escape(t['answer_text'])}</li>"
            for t in (topics or [])
        )
        content_parts.append(f"<h3>Topics</h3>\n  <ul>{topic_items}</ul>")
    content_section = "\n  ".join(content_parts)

    if hospital.portal_password_hash:
        portal_cta = (
            '<p style="margin-top: 20px;"><a class="btn-secondary" style="background: var(--sage-deep); '
            'color: #fff; border: none;" href="/portal/login">Log into bookings dashboard</a></p>'
            '<p class="hint">Use the bookings portal password you set in Step 7.</p>'
        )
    else:
        edit_url = f"/admin/edit-tenant/{hospital.id}?secret={html.escape(secret, quote=True)}"
        portal_cta = (
            '<div class="warning-banner" style="margin-top: 20px;">No bookings portal password was set, '
            f'so there\'s no way to log in yet — <a href="{edit_url}">edit this tenant</a> to add one.</div>'
        )

    return f"""<!doctype html>
<html>
<head><title>Hospital onboarded</title>{_STYLE}</head>
<body>
<div class="ok-page">
  <div class="brand">
    <div class="brand-mark">H</div>
    <span class="brand-name">Hospital Onboarding</span>
    <span class="brand-sub">— guided setup wizard</span>
  </div>
  <h1>Hospital created</h1>
  <div class="ok-box">
    <strong>{html.escape(hospital.name)}</strong> was created with hospital ID
    <strong>{hospital.id}</strong> (phone_number_id: {html.escape(hospital.whatsapp_phone_number_id)}).
  </div>

  {portal_cta}
  {warning_html}

  {content_section}
  <p class="hint">
    Reminder: this only recorded the credentials you entered — the hospital's own
    Meta Business/WhatsApp number verification and System User access token must
    already have been set up on Meta's side beforehand (Section 12.3). If that
    wasn't done first, outbound messages and webhook signature validation for
    this hospital will fail until it is.
  </p>
  <p>
    <a href="/admin/onboard-hospital">Onboard another hospital</a>
    &nbsp;·&nbsp;
    <a href="/admin/tenants?secret={html.escape(secret, quote=True)}">View all tenants</a>
  </p>
</div>
</body>
</html>"""


def _mask_secret(value: str | None) -> str:
    """Same masking rule as the wizard's own review screen (Step 8's JS
    maskSecret()) -- last 4 characters visible, everything before that
    replaced with bullets. Used for the tenant edit form's hint text, never
    for the actual input value (see _edit_tenant_html's comment on why the
    token/secret fields themselves start blank, not pre-filled with this)."""
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "••••"
    return "••••••••" + value[-4:]


def _secret_gate_html(action_path: str, label: str) -> str:
    """Shared by /admin/tenants and /admin/edit-tenant/{id}: both show
    sensitive data (existing credentials, even masked) so both need the same
    ADMIN_SECRET gate the onboarding POST already uses -- but these are GET
    pages, which can't read a submitted form field before rendering, so the
    secret travels as a query param instead (a plain GET back to the same
    URL). Same "basic protection, not production-grade auth" tradeoff this
    project already made for ADMIN_SECRET/INTERNAL_SECRET generally."""
    return f"""<!doctype html>
<html>
<head><title>{html.escape(label)}</title>{_STYLE}</head>
<body>
<div class="login-shell">
  <div class="login-card">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">Hospital Onboarding</span>
      <span class="brand-sub">— platform admin</span>
    </div>
    <h2>{html.escape(label)}</h2>
    <p class="step-desc">This page shows tenant credentials, so it's gated the same way onboarding is.</p>
    <form method="get" action="{html.escape(action_path)}">
      <label for="secret">Admin secret</label>
      <input type="password" id="secret" name="secret" required autofocus>
      <button type="submit" style="margin-top: 18px; width: 100%;">Continue</button>
    </form>
  </div>
</div>
</body>
</html>"""


def _tenants_list_html(hospitals: list, secret: str) -> str:
    def row(h) -> str:
        status_pill = (
            '<span class="pill pill-active">Active</span>' if h.is_active
            else '<span class="pill pill-inactive">Inactive</span>'
        )
        return f"""<div class="list-row">
          <div class="list-row-main">
            <span class="list-row-title">{html.escape(h.name)}</span>
            <span class="list-row-sub">#{h.id} · {html.escape(h.whatsapp_phone_number_id or "no phone_number_id set")} · {html.escape(h.data_tier)}</span>
          </div>
          <div class="list-row-meta">
            {status_pill}
            <a class="btn-secondary" href="/admin/edit-tenant/{h.id}?secret={html.escape(secret, quote=True)}">Edit</a>
          </div>
        </div>"""

    rows_html = "".join(row(h) for h in hospitals) or '<div class="empty-note">No tenants onboarded yet.</div>'

    return f"""<!doctype html>
<html>
<head><title>All tenants</title>{_STYLE}</head>
<body>
<div class="shell no-rail">
  <div class="brand-row" style="grid-column: 1 / -1;">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">Hospital Onboarding</span>
      <span class="brand-sub">— platform admin</span>
    </div>
    <div class="brand-nav">
      <a href="/admin/onboard-hospital">Onboard a hospital</a>
    </div>
  </div>
  <main class="main">
    <div class="page-header">
      <h2>All tenants</h2>
      <span class="hint">{len(hospitals)} onboarded</span>
    </div>
    <div class="card-list">{rows_html}</div>
  </main>
</div>
</body>
</html>"""


def _edit_tenant_html(hospital, errors: list[str] | None, values: dict | None, secret: str) -> str:
    v = values or {}

    def esc(key: str, default: str = "") -> str:
        return html.escape(str(v.get(key, default)))

    def checked(option: str) -> str:
        return "checked" if v.get("data_tier", hospital.data_tier) == option else ""

    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        error_html = f'<div class="error-banner"><strong>Please fix the following:</strong><ul>{items}</ul></div>'

    return f"""<!doctype html>
<html>
<head><title>Edit tenant — {html.escape(hospital.name)}</title>{_STYLE}</head>
<body>
<div class="shell no-rail">
  <div class="brand-row" style="grid-column: 1 / -1;">
    <div class="brand">
      <div class="brand-mark">H</div>
      <span class="brand-name">Hospital Onboarding</span>
      <span class="brand-sub">— platform admin</span>
    </div>
    <div class="brand-nav">
      <a href="/admin/tenants?secret={html.escape(secret, quote=True)}">All tenants</a>
    </div>
  </div>
  <main class="main">
    {error_html}
    <p class="eyebrow">Editing tenant #{hospital.id}</p>
    <h2>{html.escape(hospital.name)}</h2>
    <p class="step-desc">Only fields you change are updated — leave the token/secret fields blank to keep their current values.</p>

    <form method="post" action="/admin/edit-tenant/{hospital.id}">
      <input type="hidden" name="admin_secret" value="{html.escape(secret, quote=True)}">

      <label for="name">Hospital name</label>
      <input type="text" id="name" name="name" value="{esc('name', hospital.name)}" required>

      <label for="whatsapp_phone_number_id">WhatsApp phone_number_id</label>
      <input type="text" id="whatsapp_phone_number_id" name="whatsapp_phone_number_id"
             value="{esc('whatsapp_phone_number_id', hospital.whatsapp_phone_number_id or '')}" required>

      <label for="access_token">Access token</label>
      <input type="text" id="access_token" name="access_token" placeholder="Leave blank to keep current ({html.escape(_mask_secret(hospital.access_token))})">

      <label for="app_secret">App secret</label>
      <input type="text" id="app_secret" name="app_secret" placeholder="Leave blank to keep current ({html.escape(_mask_secret(hospital.app_secret))})">

      <label for="welcome_message_text">Welcome message text</label>
      <textarea id="welcome_message_text" name="welcome_message_text" rows="2">{esc('welcome_message_text', hospital.welcome_message_text or '')}</textarea>

      <div class="field-row">
        <div>
          <label for="reminder_offsets_hours">Reminder offsets (comma-separated hours)</label>
          <input type="text" id="reminder_offsets_hours" name="reminder_offsets_hours"
                 value="{esc('reminder_offsets_hours', ','.join(str(o) for o in hospital.reminder_offsets_hours))}">
        </div>
        <div>
          <label for="reminder_template_name">Reminder template name</label>
          <input type="text" id="reminder_template_name" name="reminder_template_name"
                 value="{esc('reminder_template_name', hospital.reminder_template_name or '')}">
        </div>
      </div>

      <label for="portal_password">Bookings portal password</label>
      <input type="password" id="portal_password" name="portal_password"
             placeholder="Leave blank to keep current ({'set' if hospital.portal_password_hash else 'not set'})">
      <p class="field-hint">Your staff logs into <a href="/portal/login">/portal/login</a> with this to see WhatsApp bookings (Tier 1 only).</p>

      <fieldset>
        <legend>Data connection</legend>
        <label class="radio-row"><input type="radio" name="data_tier" value="tier1" {checked('tier1')}> Tier 1 — this platform</label>
        <label class="radio-row"><input type="radio" name="data_tier" value="tier2" {checked('tier2')}> Tier 2 — external API</label>
        <label class="radio-row"><input type="radio" name="data_tier" value="tier3" {checked('tier3')}> Tier 3 — direct database</label>

        <label for="api_base_url">API base URL (Tier 2 only)</label>
        <input type="text" id="api_base_url" name="api_base_url" value="{esc('api_base_url', hospital.external_api_base_url or '')}">
        <label for="api_key">API key (Tier 2 only)</label>
        <input type="text" id="api_key" name="api_key" value="{esc('api_key', hospital.external_api_key or '')}">
      </fieldset>

      <div class="nav-buttons">
        <a href="/admin/tenants?secret={html.escape(secret, quote=True)}"><button type="button" class="back-btn">Cancel</button></a>
        <button type="submit">Save changes</button>
      </div>
    </form>
  </main>
</div>
</body>
</html>"""


def _edit_confirmation_html(hospital, secret: str = "") -> str:
    return f"""<!doctype html>
<html>
<head><title>Tenant updated</title>{_STYLE}</head>
<body>
<div class="ok-page">
  <div class="brand">
    <div class="brand-mark">H</div>
    <span class="brand-name">Hospital Onboarding</span>
    <span class="brand-sub">— platform admin</span>
  </div>
  <h1>Tenant updated</h1>
  <div class="ok-box">
    <strong>{html.escape(hospital.name)}</strong> (tenant #{hospital.id}) was updated.
  </div>
  <div class="warning-banner">
    <strong>This tenant's WhatsApp client is cached — changes take effect after the app restarts, not immediately.</strong>
    Any change to the access token, app secret, or phone_number_id will keep using the OLD cached credentials on an
    already-running process until it is restarted. Updating the database (which this just did) is only half of
    fixing a credential problem — the process also needs to be restarted before the new value is actually used.
  </div>
  <p><a href="/admin/tenants?secret={html.escape(secret, quote=True)}">Back to all tenants</a></p>
</div>
</body>
</html>"""


@router.get("/admin/onboard-hospital", response_class=HTMLResponse)
async def onboard_hospital_form():
    return _wizard_html(None, {}, [])


@router.post("/admin/onboard-hospital", response_class=HTMLResponse)
async def onboard_hospital_submit(
    request: Request,
    admin_secret: str = Form(""),
    name: str = Form(""),
    whatsapp_phone_number_id: str = Form(""),
    access_token: str = Form(""),
    app_secret: str = Form(""),
    welcome_message_text: str = Form(""),
    reminder_offsets_hours: str = Form(""),
    reminder_template_name: str = Form(""),
    portal_password: str = Form(""),
    enabled_features: list[str] = Form(default=[]),
    data_tier: str = Form("tier1"),
    api_base_url: str = Form(""),
    api_key: str = Form(""),
    department_name: list[str] = Form(default=[]),
    doctor_department_index: list[str] = Form(default=[]),
    doctor_name: list[str] = Form(default=[]),
    doctor_specialization: list[str] = Form(default=[]),
    doctor_qualification: list[str] = Form(default=[]),
    doctor_years_experience: list[str] = Form(default=[]),
    doctor_working_days: list[str] = Form(default=[]),
    doctor_working_hours: list[str] = Form(default=[]),
    doctor_slot_duration_minutes: list[str] = Form(default=[]),
    doctor_breaks: list[str] = Form(default=[]),
    doctor_max_bookings_per_slot: list[str] = Form(default=[]),
    doctor_daily_booking_limit: list[str] = Form(default=[]),
    doctor_online_quota: list[str] = Form(default=[]),
    doctor_walkin_quota: list[str] = Form(default=[]),
    doctor_followup_duration_minutes: list[str] = Form(default=[]),
    doctor_effective_from: list[str] = Form(default=[]),
    topic_label: list[str] = Form(default=[]),
    topic_answer: list[str] = Form(default=[]),
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
        "portal_password": portal_password,
        "enabled_features": enabled_features,
        "data_tier": data_tier,
        "api_base_url": api_base_url,
        "api_key": api_key,
    }

    # Reconstruct departments/doctors AND topics from the submitted fields
    # regardless of which features are enabled or what else is wrong, so a
    # rejected submission (e.g. wrong admin secret, duplicate phone_number_id)
    # can still be re-rendered with everything the operator entered intact,
    # not lost -- only the ones matching an enabled feature ever actually get
    # used below, but reconstructing both is cheap and keeps this simple.
    departments, dept_errors, dept_warnings = _build_departments(
        department_name, doctor_department_index, doctor_name, doctor_specialization,
        doctor_qualification, doctor_years_experience, doctor_working_days,
        doctor_working_hours, doctor_slot_duration_minutes,
        doctor_breaks, doctor_max_bookings_per_slot, doctor_daily_booking_limit,
        doctor_online_quota, doctor_walkin_quota, doctor_followup_duration_minutes, doctor_effective_from,
    )
    topics, topic_errors = _build_faq_topics(topic_label, topic_answer)

    if not check_admin_secret(admin_secret, request):
        return HTMLResponse(
            _wizard_html(["Incorrect admin secret."], values, departments, topics), status_code=403
        )

    name = name.strip()
    whatsapp_phone_number_id = whatsapp_phone_number_id.strip()
    errors = []
    if not name:
        errors.append("Hospital name is required.")
    if not whatsapp_phone_number_id:
        errors.append("WhatsApp phone_number_id is required.")

    unknown_features = [f for f in enabled_features if f not in flows.ALL_FEATURES]
    if unknown_features:
        errors.append(f'Unrecognized patient-experience option(s): {", ".join(unknown_features)}.')
    if not enabled_features:
        errors.append("At least one patient-experience option is required.")

    # SPEC Section 14.5: tier is collected once, unconditionally, regardless
    # of which features are enabled -- it's no longer forked on a single
    # exclusive flow_type.
    if data_tier not in _VALID_TIERS:
        errors.append(f'Unrecognized data connection tier "{data_tier}".')
    elif data_tier == "tier2" and not (api_base_url.strip() and api_key.strip()):
        errors.append('"Connect my existing system\'s API" requires both an API base URL and an API key.')

    if "booking" in enabled_features:
        errors.extend(dept_errors)
        if not departments:
            errors.append("At least one department with at least one doctor is required.")
    if "faq" in enabled_features:
        errors.extend(topic_errors)
        if not topics:
            errors.append("At least one topic with a label and an answer is required.")

    if errors:
        return HTMLResponse(_wizard_html(errors, values, departments, topics), status_code=400)

    offsets = _parse_offsets(reminder_offsets_hours)
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
            portal_password=portal_password.strip() or None,
            enabled_features=enabled_features,
        )
    except IntegrityError:
        errors.append(
            f'A hospital with WhatsApp phone_number_id "{whatsapp_phone_number_id}" already exists — '
            "each hospital must have its own phone_number_id for message routing to work correctly."
        )
        return HTMLResponse(_wizard_html(errors, values, departments, topics), status_code=400)

    created_departments = []
    if "booking" in enabled_features:
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
                    breaks=doc["breaks"],
                    max_bookings_per_slot=doc["max_bookings_per_slot"],
                    daily_booking_limit=doc["daily_booking_limit"],
                    online_quota=doc["online_quota"],
                    walkin_quota=doc["walkin_quota"],
                    followup_duration_minutes=doc["followup_duration_minutes"],
                    effective_from=doc["effective_from"],
                )
                for doc in dept["doctors"]
            ]
            created_departments.append({"name": created_dept["name"], "doctors": created_doctors})

    created_topics = []
    if "faq" in enabled_features:
        created_topics = [db.create_faq_topic(hospital.id, t["topic_label"], t["answer_text"]) for t in topics]

    return _confirmation_html(hospital, created_departments, admin_secret, topics=created_topics, warnings=dept_warnings)


@router.get("/admin/tenants", response_class=HTMLResponse)
async def list_tenants(request: Request, secret: str = ""):
    # A blank secret (first load of the gate page) never counts as a failed
    # attempt -- only calling check_admin_secret() when a secret was actually
    # submitted preserves the existing 200-vs-403 "just show me the form"
    # distinction while still rate-limiting real guesses.
    if not secret or not check_admin_secret(secret, request):
        return HTMLResponse(_secret_gate_html("/admin/tenants", "All tenants"), status_code=403 if secret else 200)
    hospitals = db.get_all_hospitals()
    return _tenants_list_html(hospitals, secret)


@router.get("/admin/edit-tenant/{tenant_id}", response_class=HTMLResponse)
async def edit_tenant_form(tenant_id: int, request: Request, secret: str = ""):
    if not secret or not check_admin_secret(secret, request):
        return HTMLResponse(_secret_gate_html(f"/admin/edit-tenant/{tenant_id}", "Edit tenant"), status_code=403 if secret else 200)
    hospital = db.get_hospital(tenant_id)
    if hospital is None:
        return HTMLResponse(f"<p>No tenant with id {tenant_id}.</p>", status_code=404)
    return _edit_tenant_html(hospital, None, None, secret)


@router.post("/admin/edit-tenant/{tenant_id}", response_class=HTMLResponse)
async def edit_tenant_submit(
    tenant_id: int,
    request: Request,
    admin_secret: str = Form(""),
    name: str = Form(""),
    whatsapp_phone_number_id: str = Form(""),
    access_token: str = Form(""),
    app_secret: str = Form(""),
    welcome_message_text: str = Form(""),
    reminder_offsets_hours: str = Form(""),
    reminder_template_name: str = Form(""),
    portal_password: str = Form(""),
    data_tier: str = Form("tier1"),
    api_base_url: str = Form(""),
    api_key: str = Form(""),
):
    hospital = db.get_hospital(tenant_id)
    if hospital is None:
        return HTMLResponse(f"<p>No tenant with id {tenant_id}.</p>", status_code=404)

    values = {
        "name": name,
        "whatsapp_phone_number_id": whatsapp_phone_number_id,
        "welcome_message_text": welcome_message_text,
        "reminder_offsets_hours": reminder_offsets_hours,
        "reminder_template_name": reminder_template_name,
        "data_tier": data_tier,
        "api_base_url": api_base_url,
        "api_key": api_key,
    }

    if not check_admin_secret(admin_secret, request):
        return HTMLResponse(_edit_tenant_html(hospital, ["Incorrect admin secret."], values, admin_secret), status_code=403)

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

    if errors:
        return HTMLResponse(_edit_tenant_html(hospital, errors, values, admin_secret), status_code=400)

    offsets = _parse_offsets(reminder_offsets_hours)
    stored_api_base_url = api_base_url.strip() or None if data_tier == "tier2" else None
    stored_api_key = api_key.strip() or None if data_tier == "tier2" else None

    # Blank token/secret fields mean "keep the current value" -- the form never
    # pre-fills these with the real secret (only a masked hint), so a blank
    # submission is the normal case, not an explicit request to erase it.
    new_access_token = access_token.strip() or hospital.access_token
    new_app_secret = app_secret.strip() or hospital.app_secret
    # Same "blank keeps current" rule as the token/secret fields above -- the
    # form never shows the real password (there's nothing to show, it's
    # hashed), only a "keep current" hint, so hashing a blank submission
    # would silently replace a real password with a hash of "".
    new_portal_password_hash = (
        db.hash_portal_password(portal_password.strip()) if portal_password.strip() else hospital.portal_password_hash
    )

    try:
        updated = db.update_hospital(
            tenant_id,
            name=name,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            access_token=new_access_token,
            app_secret=new_app_secret,
            timezone=hospital.timezone,
            welcome_message_text=welcome_message_text.strip() or None,
            reminder_offsets_hours=offsets,
            reminder_template_name=reminder_template_name.strip() or None,
            data_tier=data_tier,
            external_api_base_url=stored_api_base_url,
            external_api_key=stored_api_key,
            portal_password_hash=new_portal_password_hash,
            enabled_features=hospital.enabled_features,
            feature_labels=hospital.feature_labels,
            closing_message_text=hospital.closing_message_text,
            business_hours_text=hospital.business_hours_text,
            default_language=hospital.default_language,
            language_prompt_enabled=hospital.language_prompt_enabled,
            session_timeout_minutes=hospital.session_timeout_minutes,
        )
    except IntegrityError:
        errors.append(
            f'A hospital with WhatsApp phone_number_id "{whatsapp_phone_number_id}" already exists — '
            "each hospital must have its own phone_number_id for message routing to work correctly."
        )
        return HTMLResponse(_edit_tenant_html(hospital, errors, values, admin_secret), status_code=400)

    return _edit_confirmation_html(updated, admin_secret)
