# admin/onboarding.py
"""
Section 15 follow-up: the real onboarding UI is the Next.js wizard
(frontend/src/components/onboarding/OnboardingWizard.tsx, submitting to
admin/onboarding_api.py's JSON endpoint) and the real platform-admin tenant
UI is the Next.js pages under frontend/src/app/admin/ (submitting to
admin/tenants_api.py). This module used to ALSO serve a full parallel
server-rendered HTML wizard and HTML tenant list/edit pages -- genuinely
redundant once the Next.js versions existed, so removed. What's left:

1. Shared validation/parsing helpers (_validate_doctor_fields,
   _build_departments, _build_faq_topics, _parse_offsets, _mask_secret,
   check_admin_secret/ADMIN_SECRET, _VALID_TIERS) -- imported directly by
   admin/onboarding_api.py, admin/tenants_api.py, and portal_api.py, so this
   module stays even though its own HTML routes don't.
2. Two minimal "admin" / "superadmin" entry-point pages (below) -- each just
   a button linking to the real Next.js page, for anyone who still has the
   backend's own URL bookmarked. No forms, no state, nothing to keep in
   sync with the JSON API's own validation.
"""
import hmac
import os
import re
from datetime import date, datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

import core.rate_limit as rate_limit
from admin.theme import STYLE as _STYLE

router = APIRouter()

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

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



def _mask_secret(value: str | None) -> str:
    """Same masking rule the Next.js edit-tenant page shows as a hint --
    last 4 characters visible, everything before that replaced with
    bullets. Used by admin/tenants_api.py's tenant-detail response, never
    for the actual credential value."""
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "\u2022\u2022\u2022\u2022"
    return "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" + value[-4:]


def _button_page(eyebrow: str, title: str, description: str, button_label: str, button_href: str) -> str:
    """Shared by both minimal pages below -- a single centered card with one
    button, nothing else. Real functionality (forms, validation, tenant
    data) lives entirely in the Next.js frontend these buttons link to."""
    return f"""<!doctype html>
<html>
<head><title>{title} \u2014 CareConnect</title>{_STYLE}</head>
<body>
<div class="ok-page">
  <div class="brand">
    <div class="brand-mark">H</div>
    <span class="brand-name">{eyebrow}</span>
  </div>
  <h1>{title}</h1>
  <p class="hint">{description}</p>
  <p><a class="btn-secondary" style="background: var(--sage-deep); color: #fff; border: none;" href="{button_href}">{button_label}</a></p>
</div>
</body>
</html>"""


@router.get("/admin/onboard-hospital", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Minimal entry point -- the real guided wizard (Google sign-in +
    ADMIN_SECRET, Section 15) lives at {FRONTEND_ORIGIN}/auth. Ungated:
    there's nothing sensitive on this page, only a link onward to where the
    real gates are enforced."""
    return _button_page(
        "DAAP CareConnect", "Admin", "Onboard a new hospital through the guided setup wizard.",
        "Open onboarding wizard", f"{FRONTEND_ORIGIN}/auth",
    )


@router.get("/admin/tenants", response_class=HTMLResponse)
async def superadmin_page(request: Request):
    """Minimal entry point -- the real tenant list/edit UI (gated by
    TENANTS_ADMIN_SECRET, admin/tenants_api.py) lives at
    {FRONTEND_ORIGIN}/admin/tenants. Ungated here for the same reason as
    admin_page() above -- this page itself shows nothing sensitive."""
    return _button_page(
        "DAAP CareConnect", "Super Admin", "View and edit every onboarded hospital's configuration.",
        "Open tenant admin", f"{FRONTEND_ORIGIN}/admin/tenants",
    )
