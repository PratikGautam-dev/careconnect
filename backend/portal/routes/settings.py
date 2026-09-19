import re

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from admin.validation import _parse_offsets
import db.repository as db
from core.rate_limit import client_ip
from core.translations import SUPPORTED_LANGUAGES
from db.repositories.handoffs import DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS
from db.repositories.hospital_settings import (
    DEFAULT_APPOINTMENT_DURATION_MINUTES, DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS,
    DEFAULT_ATTENDANCE_EARLY_CHECKIN_MINUTES, DEFAULT_ATTENDANCE_LATE_THRESHOLD_MINUTES, DEFAULT_BUFFER_MINUTES,
    DEFAULT_FOLLOWUP_VALIDITY_DAYS, DEFAULT_FUTURE_BOOKING_DAYS,
)
from modules.google_calendar import is_calendar_integration_configured
from portal.deps import _authenticate, get_current_staff, require_capability, require_permission

router = APIRouter()

# Minutes bounds mirror db/schema.sql's session_timeout_minutes
# CHECK constraint exactly -- validated here too so a bad value gets a clear
# 400 from this endpoint instead of surfacing as a raw IntegrityError from
# the DB constraint.
_MIN_SESSION_TIMEOUT_MINUTES = 2
_MAX_SESSION_TIMEOUT_MINUTES = 120

# Bounds for hospitals.handoff_auto_resolve_hours,
# same "validate here for a clean 400" reasoning as the session-timeout
# bounds above. 1 hour minimum (shorter would risk auto-resolving a handoff
# staff simply hasn't gotten to yet within a normal shift), 1 week maximum
# (longer defeats the point of "don't leave it open indefinitely").
_MIN_HANDOFF_AUTO_RESOLVE_HOURS = 1
_MAX_HANDOFF_AUTO_RESOLVE_HOURS = 168

# Follow-up eligibility window: same "validate here for a clean 400" reasoning as the
# bounds above. 1 day minimum (0 would mean no follow-up is ever eligible);
# 365 maximum is a generous ceiling against a fat-fingered entry.
_MIN_FOLLOWUP_VALIDITY_DAYS = 1
_MAX_FOLLOWUP_VALIDITY_DAYS = 365
# Fee ceiling is just a fat-finger guard (₹1,000,000), not a considered
# product limit -- consultation fees are always non-negative (DB CHECK
# constraint already enforces that floor).
_MAX_FEE = 1_000_000

# Slot-generation window: same "validate here for a clean
# 400" reasoning as the bounds above. 1 day minimum (0 would mean nothing is
# ever bookable); 90 days is a generous ceiling -- long past what any patient
# realistically books that far ahead, and keeps generate_slots_for_*()'s
# per-entity candidate-building bounded.
_MIN_FUTURE_BOOKING_DAYS = 1
_MAX_FUTURE_BOOKING_DAYS = 60

# Same "validate here
# for a clean 400" reasoning as the bounds above.
_MIN_APPOINTMENT_DURATION_MINUTES = 5
_MAX_APPOINTMENT_DURATION_MINUTES = 240
_MIN_BUFFER_MINUTES = 0
_MAX_BUFFER_MINUTES = 120
_MIN_MAX_APPOINTMENTS_PER_DAY = 1
_MAX_MAX_APPOINTMENTS_PER_DAY = 100_000

# Settings -> Attendance tab: same "validate here
# for a clean 400" reasoning as the bounds above.
_MIN_ATTENDANCE_RADIUS_METERS = 10
_MAX_ATTENDANCE_RADIUS_METERS = 5_000
_MIN_ATTENDANCE_WINDOW_MINUTES = 0
_MAX_ATTENDANCE_WINDOW_MINUTES = 240
# Auto-checkout grace period: generous ceiling
# (12 hours) against a fat-fingered entry -- 0 is a valid, meaningful value
# ("close it out right at shift end, no grace at all").
_MIN_ATTENDANCE_GRACE_MINUTES = 0
_MAX_ATTENDANCE_GRACE_MINUTES = 720
_MIN_LATITUDE, _MAX_LATITUDE = -90.0, 90.0
_MIN_LONGITUDE, _MAX_LONGITUDE = -180.0, 180.0
_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_bounded_int(raw, field_name, unit, lo, hi):
    """Shared by portal_update_settings() and portal_update_attendance_
    settings() below -- was a nested function inside the former only, which
    left the latter unable to call it at all (a NameError at request time,
    not import time, so nothing caught it until Settings -> Attendance's
    save was actually exercised)."""
    if raw in (None, ""):
        return None, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, JSONResponse({"error": f"{field_name} must be a whole number of {unit}."}, status_code=400)
    if not (lo <= value <= hi):
        return None, JSONResponse({"error": f"{field_name} must be between {lo} and {hi}."}, status_code=400)
    return value, None


@router.get("/api/portal/settings")
async def portal_get_settings(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    hospital_settings = db.get_hospital_settings(hospital.id)
    return JSONResponse(
        {
            "name": hospital.name,
            "welcome_message_text": hospital.welcome_message_text or "",
            "reminder_offsets_hours": ",".join(str(h) for h in hospital.reminder_offsets_hours),
            "reminder_template_name": hospital.reminder_template_name or "",
            # Self-serve bot customization.
            "enabled_features": hospital.enabled_features,
            "closing_message_text": hospital.closing_message_text or "",
            "business_hours_text": hospital.business_hours_text or "",
            "default_language": hospital.default_language,
            "language_prompt_enabled": hospital.language_prompt_enabled,
            "session_timeout_minutes": hospital.session_timeout_minutes or 30,
            "handoff_auto_resolve_hours": hospital.handoff_auto_resolve_hours or DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS,
            # Unlike enabled_features (operator-only, /admin/edit-tenant),
            # these two ARE genuine self-serve bot customization -- same
            # category as closing_message_text/business_hours_text above.
            "require_patient_confirmation": hospital.require_patient_confirmation,
            # Per-hospital Follow-up settings
            # (db/repositories/hospital_settings.py), not columns on `hospitals` itself.
            "followup_validity_days": hospital_settings["followup_validity_days"] or DEFAULT_FOLLOWUP_VALIDITY_DAYS,
            "followup_fee": hospital_settings["followup_fee"],
            "new_consultation_fee": hospital_settings["new_consultation_fee"],
            # Flat fee added to a home-collection
            # Lab Test booking's price review.
            "home_collection_charge": hospital_settings["home_collection_charge"],
            # How many days ahead doctor/resource/
            # procedure slots are generated.
            "future_booking_days": hospital_settings["future_booking_days"] or DEFAULT_FUTURE_BOOKING_DAYS,
            # The
            # first two are self-serve settings (writable via POST below);
            # appointments_today_count is read-only, live data for the
            # "X out of Y" progress bar next to max_appointments_per_day --
            # not stored anywhere, not part of the POST body.
            "default_appointment_duration_minutes": (
                hospital_settings["default_appointment_duration_minutes"] or DEFAULT_APPOINTMENT_DURATION_MINUTES
            ),
            "buffer_minutes": hospital_settings["buffer_minutes"] or DEFAULT_BUFFER_MINUTES,
            "max_appointments_per_day": hospital_settings["max_appointments_per_day"],
            "appointments_today_count": db.get_hospital_booked_appointments_today_count(hospital.id),
        },
        # Defensive -- rules out any browser/CDN-level HTTP caching of this
        # authenticated GET as a contributing factor in a stale-settings read.
        headers={"Cache-Control": "no-store"},
    )


@router.post("/api/portal/settings")
async def portal_update_settings(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    # Validation -- a clear 400 instead of a raw DB error/silent
    # bad value.
    default_language = payload.get("default_language") or "en"
    if default_language not in SUPPORTED_LANGUAGES:
        return JSONResponse({"error": f"default_language must be one of {sorted(SUPPORTED_LANGUAGES)}."}, status_code=400)

    session_timeout_raw = payload.get("session_timeout_minutes")
    if session_timeout_raw in (None, ""):
        session_timeout_minutes = None
    else:
        try:
            session_timeout_minutes = int(session_timeout_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "session_timeout_minutes must be a whole number of minutes."}, status_code=400)
        if not (_MIN_SESSION_TIMEOUT_MINUTES <= session_timeout_minutes <= _MAX_SESSION_TIMEOUT_MINUTES):
            return JSONResponse({
                "error": f"session_timeout_minutes must be between {_MIN_SESSION_TIMEOUT_MINUTES} and {_MAX_SESSION_TIMEOUT_MINUTES}.",
            }, status_code=400)

    handoff_hours_raw = payload.get("handoff_auto_resolve_hours")
    if handoff_hours_raw in (None, ""):
        handoff_auto_resolve_hours = None
    else:
        try:
            handoff_auto_resolve_hours = int(handoff_hours_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "handoff_auto_resolve_hours must be a whole number of hours."}, status_code=400)
        if not (_MIN_HANDOFF_AUTO_RESOLVE_HOURS <= handoff_auto_resolve_hours <= _MAX_HANDOFF_AUTO_RESOLVE_HOURS):
            return JSONResponse({
                "error": f"handoff_auto_resolve_hours must be between {_MIN_HANDOFF_AUTO_RESOLVE_HOURS} and {_MAX_HANDOFF_AUTO_RESOLVE_HOURS}.",
            }, status_code=400)

    followup_days_raw = payload.get("followup_validity_days")
    if followup_days_raw in (None, ""):
        followup_validity_days = None
    else:
        try:
            followup_validity_days = int(followup_days_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "followup_validity_days must be a whole number of days."}, status_code=400)
        if not (_MIN_FOLLOWUP_VALIDITY_DAYS <= followup_validity_days <= _MAX_FOLLOWUP_VALIDITY_DAYS):
            return JSONResponse({
                "error": f"followup_validity_days must be between {_MIN_FOLLOWUP_VALIDITY_DAYS} and {_MAX_FOLLOWUP_VALIDITY_DAYS}.",
            }, status_code=400)

    future_booking_days_raw = payload.get("future_booking_days")
    if future_booking_days_raw in (None, ""):
        future_booking_days = None
    else:
        try:
            future_booking_days = int(future_booking_days_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "future_booking_days must be a whole number of days."}, status_code=400)
        if not (_MIN_FUTURE_BOOKING_DAYS <= future_booking_days <= _MAX_FUTURE_BOOKING_DAYS):
            return JSONResponse({
                "error": f"future_booking_days must be between {_MIN_FUTURE_BOOKING_DAYS} and {_MAX_FUTURE_BOOKING_DAYS}.",
            }, status_code=400)

    default_appointment_duration_minutes, error = _parse_bounded_int(
        payload.get("default_appointment_duration_minutes"), "default_appointment_duration_minutes", "minutes",
        _MIN_APPOINTMENT_DURATION_MINUTES, _MAX_APPOINTMENT_DURATION_MINUTES,
    )
    if error:
        return error
    buffer_minutes, error = _parse_bounded_int(
        payload.get("buffer_minutes"), "buffer_minutes", "minutes", _MIN_BUFFER_MINUTES, _MAX_BUFFER_MINUTES,
    )
    if error:
        return error
    max_appointments_per_day, error = _parse_bounded_int(
        payload.get("max_appointments_per_day"), "max_appointments_per_day", "appointments",
        _MIN_MAX_APPOINTMENTS_PER_DAY, _MAX_MAX_APPOINTMENTS_PER_DAY,
    )
    if error:
        return error

    def _parse_fee(raw, field_name):
        if raw in (None, ""):
            return None, None
        try:
            fee = float(raw)
        except (TypeError, ValueError):
            return None, JSONResponse({"error": f"{field_name} must be a number."}, status_code=400)
        if not (0 <= fee <= _MAX_FEE):
            return None, JSONResponse({"error": f"{field_name} must be between 0 and {_MAX_FEE}."}, status_code=400)
        return fee, None

    followup_fee, error = _parse_fee(payload.get("followup_fee"), "followup_fee")
    if error:
        return error
    new_consultation_fee, error = _parse_fee(payload.get("new_consultation_fee"), "new_consultation_fee")
    if error:
        return error
    home_collection_charge, error = _parse_fee(payload.get("home_collection_charge"), "home_collection_charge")
    if error:
        return error

    # Same restriction as portal.py's own settings form: credentials/data_tier/
    # portal_password_hash/enabled_features are never touched here, only
    # passed through unchanged -- WhatsApp connection details stay
    # operator-only via /admin/edit-tenant.
    db.update_hospital(
        hospital.id,
        name=hospital.name,
        whatsapp_phone_number_id=hospital.whatsapp_phone_number_id,
        access_token=hospital.access_token,
        app_secret=hospital.app_secret,
        timezone=hospital.timezone,
        welcome_message_text=(payload.get("welcome_message_text") or "").strip() or None,
        reminder_offsets_hours=_parse_offsets(payload.get("reminder_offsets_hours") or ""),
        reminder_template_name=(payload.get("reminder_template_name") or "").strip() or None,
        data_tier=hospital.data_tier,
        external_api_base_url=hospital.external_api_base_url,
        external_api_key=hospital.external_api_key,
        portal_password_hash=hospital.portal_password_hash,
        enabled_features=hospital.enabled_features,
        # feature_labels is not a per-hospital, self-serve setting (lives
        # on platform_settings) -- passed through unchanged, same
        # "operator-only, never touched here" discipline as enabled_features above.
        feature_labels=hospital.feature_labels,
        closing_message_text=(payload.get("closing_message_text") or "").strip() or None,
        business_hours_text=(payload.get("business_hours_text") or "").strip() or None,
        default_language=default_language,
        language_prompt_enabled=bool(payload.get("language_prompt_enabled", True)),
        session_timeout_minutes=session_timeout_minutes,
        handoff_auto_resolve_hours=handoff_auto_resolve_hours,
        require_patient_confirmation=bool(payload.get("require_patient_confirmation", False)),
        # Not self-serve -- passed straight through unchanged, same
        # discipline every other operator-only field on this call already
        # follows (enabled_features, portal_password_hash, ...). Only
        # admin/tenants_api.py's tenant-edit endpoint actually changes these.
        tenant_type=hospital.tenant_type,
        admin_capabilities=hospital.admin_capabilities,
        # Same "moved to platform_settings, pass through
        # unchanged" treatment as feature_labels above.
        dpdp_consent_required=hospital.dpdp_consent_required,
    )
    # update_hospital_settings() is always a full-object save (its own
    # docstring) -- this route doesn't own the attendance_* fields at all
    # (Settings -> Attendance's own POST does), so they must be read back
    # and passed through UNCHANGED here, exactly like portal_update_
    # attendance_settings() below already does in the other direction.
    # Missing this the first time round was a real bug: saving General
    # settings was silently wiping every Attendance setting back to NULL,
    # since omitting a kwarg here defaults it to None, not "leave as-is".
    current_attendance_settings = db.get_hospital_settings(hospital.id)
    db.update_hospital_settings(
        hospital.id, followup_validity_days=followup_validity_days,
        followup_fee=followup_fee, new_consultation_fee=new_consultation_fee,
        home_collection_charge=home_collection_charge, future_booking_days=future_booking_days,
        default_appointment_duration_minutes=default_appointment_duration_minutes, buffer_minutes=buffer_minutes,
        max_appointments_per_day=max_appointments_per_day,
        attendance_latitude=current_attendance_settings["attendance_latitude"],
        attendance_longitude=current_attendance_settings["attendance_longitude"],
        attendance_allowed_radius_meters=current_attendance_settings["attendance_allowed_radius_meters"],
        attendance_allowed_ip_cidrs=current_attendance_settings["attendance_allowed_ip_cidrs"],
        attendance_shift_start=current_attendance_settings["attendance_shift_start"],
        attendance_shift_end=current_attendance_settings["attendance_shift_end"],
        attendance_early_checkin_minutes=current_attendance_settings["attendance_early_checkin_minutes"],
        attendance_late_threshold_minutes=current_attendance_settings["attendance_late_threshold_minutes"],
        attendance_auto_checkout_grace_minutes=current_attendance_settings["attendance_auto_checkout_grace_minutes"],
    )
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "settings.update",
        entity_type="hospital", entity_id=str(hospital.id),
        before={"default_language": hospital.default_language, "session_timeout_minutes": hospital.session_timeout_minutes},
        after={"default_language": default_language, "session_timeout_minutes": session_timeout_minutes},
    )
    return JSONResponse({"ok": True})


def _parse_ip_cidrs(raw) -> tuple[str | None, JSONResponse | None]:
    """Comma-separated exact IPs and/or CIDR ranges -- validated eagerly so
    a typo'd entry gets a clear 400 now, not a silent always-fails IP check
    later (db/repositories/attendance.py's _verify_ip() itself skips any
    entry it can't parse, deliberately lenient there since that runs on
    every check-in; here, at save time, is the one place a mistake is worth
    surfacing loudly)."""
    import ipaddress

    if raw in (None, ""):
        return None, None
    entries = [e.strip() for e in str(raw).split(",") if e.strip()]
    for entry in entries:
        try:
            ipaddress.ip_network(entry, strict=False) if "/" in entry else ipaddress.ip_address(entry)
        except ValueError:
            return None, JSONResponse({"error": f"'{entry}' is not a valid IP address or CIDR range."}, status_code=400)
    return ",".join(entries), None


def _parse_hhmm(raw, field_name: str) -> tuple[str | None, JSONResponse | None]:
    if raw in (None, ""):
        return None, None
    if not _HHMM_RE.match(str(raw)):
        return None, JSONResponse({"error": f"{field_name} must be in HH:MM 24-hour format."}, status_code=400)
    return raw, None


@router.get("/api/portal/settings/attendance")
async def portal_get_attendance_settings(request: Request, authorization: str | None = Header(default=None)):
    """Settings -> Attendance tab: the geofence/IP/shift-window policy
    check_in()/check_out() (db/repositories/attendance.py) validate every
    check-in/out attempt against. A SEPARATE endpoint from GET /api/portal/
    settings (not more fields folded into that shared, full-object save) --
    gated by the "attendance_settings" page_key (admin-only by
    default), unlike that older endpoint's
    hospital-only _authenticate(), since this configuration is sensitive
    enough (an unlocked geofence radius lets anyone check in from anywhere)
    to need a real per-role check, not just a UI-level hide.

    detected_ip: whoever loads this page IS, in the
    common case, standing on the hospital's own network they're trying to
    whitelist -- so this is the exact same IP check_in()'s own geofence
    check would see from them, surfaced directly instead of asking a
    non-technical admin to read server logs or an external "what's my IP"
    site (which may not even match, behind a work VPN/proxy)."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "attendance_settings", "view")
    if forbidden:
        return forbidden
    s = db.get_hospital_settings(principal.hospital.id)
    return JSONResponse({
        "attendance_latitude": s["attendance_latitude"],
        "attendance_longitude": s["attendance_longitude"],
        "attendance_allowed_radius_meters": s["attendance_allowed_radius_meters"] or DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS,
        "attendance_allowed_ip_cidrs": s["attendance_allowed_ip_cidrs"] or "",
        "attendance_shift_start": s["attendance_shift_start"] or "",
        "attendance_shift_end": s["attendance_shift_end"] or "",
        "attendance_early_checkin_minutes": s["attendance_early_checkin_minutes"] or DEFAULT_ATTENDANCE_EARLY_CHECKIN_MINUTES,
        "attendance_late_threshold_minutes": s["attendance_late_threshold_minutes"] or DEFAULT_ATTENDANCE_LATE_THRESHOLD_MINUTES,
        # Unlike the fields above, no code-level default -- NULL genuinely
        # means "auto-checkout is off" (same "NULL means no cap" convention
        # as max_appointments_per_day), not "use some default grace period"
        # a hospital never actually opted into.
        "attendance_auto_checkout_grace_minutes": s["attendance_auto_checkout_grace_minutes"],
        "detected_ip": client_ip(request),
    }, headers={"Cache-Control": "no-store"})


@router.post("/api/portal/settings/attendance")
async def portal_update_attendance_settings(payload: dict, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "attendance_settings", "write")
    if forbidden:
        return forbidden

    lat_raw, lng_raw = payload.get("attendance_latitude"), payload.get("attendance_longitude")
    if (lat_raw in (None, "")) != (lng_raw in (None, "")):
        return JSONResponse({"error": "Set both latitude and longitude, or leave both blank."}, status_code=400)
    attendance_latitude = attendance_longitude = None
    if lat_raw not in (None, ""):
        try:
            attendance_latitude, attendance_longitude = float(lat_raw), float(lng_raw)
        except (TypeError, ValueError):
            return JSONResponse({"error": "Latitude/longitude must be numbers."}, status_code=400)
        if not (_MIN_LATITUDE <= attendance_latitude <= _MAX_LATITUDE):
            return JSONResponse({"error": f"Latitude must be between {_MIN_LATITUDE} and {_MAX_LATITUDE}."}, status_code=400)
        if not (_MIN_LONGITUDE <= attendance_longitude <= _MAX_LONGITUDE):
            return JSONResponse({"error": f"Longitude must be between {_MIN_LONGITUDE} and {_MAX_LONGITUDE}."}, status_code=400)

    attendance_allowed_radius_meters, error = _parse_bounded_int(
        payload.get("attendance_allowed_radius_meters"), "attendance_allowed_radius_meters", "meters",
        _MIN_ATTENDANCE_RADIUS_METERS, _MAX_ATTENDANCE_RADIUS_METERS,
    )
    if error:
        return error
    attendance_allowed_ip_cidrs, error = _parse_ip_cidrs(payload.get("attendance_allowed_ip_cidrs"))
    if error:
        return error
    attendance_shift_start, error = _parse_hhmm(payload.get("attendance_shift_start"), "attendance_shift_start")
    if error:
        return error
    attendance_shift_end, error = _parse_hhmm(payload.get("attendance_shift_end"), "attendance_shift_end")
    if error:
        return error
    attendance_auto_checkout_grace_minutes, error = _parse_bounded_int(
        payload.get("attendance_auto_checkout_grace_minutes"), "attendance_auto_checkout_grace_minutes", "minutes",
        _MIN_ATTENDANCE_GRACE_MINUTES, _MAX_ATTENDANCE_GRACE_MINUTES,
    )
    if error:
        return error
    attendance_early_checkin_minutes, error = _parse_bounded_int(
        payload.get("attendance_early_checkin_minutes"), "attendance_early_checkin_minutes", "minutes",
        _MIN_ATTENDANCE_WINDOW_MINUTES, _MAX_ATTENDANCE_WINDOW_MINUTES,
    )
    if error:
        return error
    attendance_late_threshold_minutes, error = _parse_bounded_int(
        payload.get("attendance_late_threshold_minutes"), "attendance_late_threshold_minutes", "minutes",
        _MIN_ATTENDANCE_WINDOW_MINUTES, _MAX_ATTENDANCE_WINDOW_MINUTES,
    )
    if error:
        return error

    # update_hospital_settings() is always a full-object save (its own
    # docstring) -- carry every OTHER hospital_settings field through
    # unchanged, same "read-then-write-back-unchanged" discipline
    # portal_update_settings() above already follows for `hospitals` columns
    # it doesn't itself own.
    current = db.get_hospital_settings(principal.hospital.id)
    db.update_hospital_settings(
        principal.hospital.id,
        followup_validity_days=current["followup_validity_days"], followup_fee=current["followup_fee"],
        new_consultation_fee=current["new_consultation_fee"], home_collection_charge=current["home_collection_charge"],
        future_booking_days=current["future_booking_days"],
        default_appointment_duration_minutes=current["default_appointment_duration_minutes"],
        buffer_minutes=current["buffer_minutes"], max_appointments_per_day=current["max_appointments_per_day"],
        attendance_latitude=attendance_latitude, attendance_longitude=attendance_longitude,
        attendance_allowed_radius_meters=attendance_allowed_radius_meters,
        attendance_allowed_ip_cidrs=attendance_allowed_ip_cidrs,
        attendance_shift_start=attendance_shift_start, attendance_shift_end=attendance_shift_end,
        attendance_early_checkin_minutes=attendance_early_checkin_minutes,
        attendance_late_threshold_minutes=attendance_late_threshold_minutes,
        attendance_auto_checkout_grace_minutes=attendance_auto_checkout_grace_minutes,
    )
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>",
        "settings.attendance_update", entity_type="hospital", entity_id=str(principal.hospital.id),
    )
    return JSONResponse({"ok": True})


@router.get("/api/portal/audit-log")
async def portal_audit_log(authorization: str | None = Header(default=None)):
    """This tenant's own 'portal'-level audit rows only -- never
    'platform_admin' rows (data_tier/API-key/tenant_type changes stay
    operator-only, visible through admin/tenants_api.py's own audit-log
    route instead). Gated by manage_settings, same capability that already
    gates this file's own settings-update route, rather than inventing a
    new one just for reading history."""
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_settings")
    if forbidden:
        return forbidden
    return JSONResponse({"entries": db.get_audit_logs(hospital_id=hospital.id, actor_level="portal")})


# --- Google Meet integration ---
#
# One Google account connected per HOSPITAL by an admin, used for every
# doctor's tele-consultation Meet links -- not a per-doctor connection
# (confirmed with the user). Deliberately gated with the newer, genuinely
# role-aware get_current_staff()/require_permission() pair rather than this
# file's own older _authenticate()/require_capability(hospital, ...)
# pattern every other route above uses: those gate by TENANT PLAN
# (capability), not by STAFF ROLE, so a receptionist's own valid session
# would pass them -- initiating or revoking the hospital's shared Google
# account connection is sensitive enough to warrant the stricter, real
# admin-only check every time, not just a UI-level hide.

@router.get("/api/portal/calendar/status")
async def portal_calendar_status(authorization: str | None = Header(default=None)):
    """The hospital admin's own Settings page reads this to decide what to
    render -- `configured=False` means the feature itself isn't set up yet
    (GOOGLE_CALENDAR_CLIENT_ID/SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY unset),
    a clean, expected state this whole build was required to degrade
    gracefully through, not an error."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "settings", "view")
    if forbidden:
        return forbidden
    connection = db.get_calendar_connection(principal.hospital.id) if is_calendar_integration_configured() else None
    return JSONResponse({
        "configured": is_calendar_integration_configured(),
        "connected": connection is not None,
        "google_email": connection["google_email"] if connection else None,
    })


@router.post("/api/portal/calendar/disconnect")
async def portal_calendar_disconnect(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "settings", "write")
    if forbidden:
        return forbidden
    db.delete_calendar_connection(principal.hospital.id)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>",
        "settings.google_calendar_disconnect", entity_type="hospital", entity_id=str(principal.hospital.id),
    )
    return JSONResponse({"ok": True})
