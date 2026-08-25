# admin/validation.py
"""
Shared field validators, split out of admin/onboarding.py (Section 15
follow-up's leftover shared-helpers module) since _validate_doctor_fields
and _parse_offsets are imported directly by admin/onboarding_api.py,
admin/tenants_api.py, and portal/routes/{doctors,settings}.py -- a
private-function cross-import from admin/onboarding.py into the portal
package, fixed by giving these a home that isn't otherwise "admin-only"
business logic (check_admin_secret, the HTML entry-point pages, _mask_secret,
_build_departments/_build_faq_topics all stay in admin/onboarding.py --
those are wizard/tenant-admin specific, not generic field validation).
"""
import re
from datetime import date, datetime

_WEEKDAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_WEEKDAY_SET = set(_WEEKDAY_ABBREVS)
_TIME_RANGE_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")


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
