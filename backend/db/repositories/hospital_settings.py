# db/repositories/hospital_settings.py
"""Per-hospital self-serve settings that don't belong as more columns on the
already very wide `hospitals` table (confirmed with the user) -- a
per-hospital counterpart to db/repositories/platform_settings.py's global
singleton. One row per hospital_id, created lazily (get_hospital_settings()
upserts a blank row on first read) rather than at hospital-creation time, so
this table didn't need every hospital-creation code path (create_hospital(),
db/seed.py, admin onboarding) touched to introduce it."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.orm_models import HospitalSettings

# The code-level default when a hospital's own followup_validity_days is
# NULL (never configured).
DEFAULT_FOLLOWUP_VALIDITY_DAYS = 30

# The code-level default when a hospital's own future_booking_days is NULL
# (never configured).
DEFAULT_FUTURE_BOOKING_DAYS = 14

# The code-level default when a hospital's own
# default_appointment_duration_minutes is NULL (never configured) --
# applied to any doctor whose own slot_duration_minutes is also unset
# (db/repositories/doctors.py).
DEFAULT_APPOINTMENT_DURATION_MINUTES = 30
# NULL means no gap between slots.
DEFAULT_BUFFER_MINUTES = 0

# Settings -> Attendance tab: code-level defaults applied only once a
# hospital HAS set attendance_latitude/longitude -- unlike the fields
# above, there's no meaningful default for the geofence/IP checks
# themselves being "on" (see db/repositories/attendance.py's check_in(),
# which skips a check entirely when its own setting is NULL).
DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS = 150
DEFAULT_ATTENDANCE_EARLY_CHECKIN_MINUTES = 30
DEFAULT_ATTENDANCE_LATE_THRESHOLD_MINUTES = 10


def get_hospital_settings(hospital_id: int) -> dict:
    """Always returns a row (upserting a blank one first if this hospital has
    never had its settings touched) -- callers never need a None check, same
    "the row always exists in practice" guarantee platform_settings' bootstrap
    gives its own singleton."""
    session = get_session()
    session.execute(
        pg_insert(HospitalSettings)
        .values(hospital_id=hospital_id)
        .on_conflict_do_nothing(index_elements=["hospital_id"])
    )
    session.commit()
    row = session.execute(
        select(HospitalSettings).where(HospitalSettings.hospital_id == hospital_id)
    ).scalar_one()
    return {
        "followup_validity_days": row.followup_validity_days,
        "followup_fee": float(row.followup_fee) if row.followup_fee is not None else None,
        "new_consultation_fee": float(row.new_consultation_fee) if row.new_consultation_fee is not None else None,
        "home_collection_charge": (
            float(row.home_collection_charge) if row.home_collection_charge is not None else None
        ),
        "future_booking_days": row.future_booking_days,
        "default_appointment_duration_minutes": row.default_appointment_duration_minutes,
        "buffer_minutes": row.buffer_minutes,
        "max_appointments_per_day": row.max_appointments_per_day,
        "attendance_latitude": float(row.attendance_latitude) if row.attendance_latitude is not None else None,
        "attendance_longitude": float(row.attendance_longitude) if row.attendance_longitude is not None else None,
        "attendance_allowed_radius_meters": row.attendance_allowed_radius_meters,
        "attendance_allowed_ip_cidrs": row.attendance_allowed_ip_cidrs,
        "attendance_shift_start": row.attendance_shift_start,
        "attendance_shift_end": row.attendance_shift_end,
        "attendance_early_checkin_minutes": row.attendance_early_checkin_minutes,
        "attendance_late_threshold_minutes": row.attendance_late_threshold_minutes,
        "attendance_auto_checkout_grace_minutes": row.attendance_auto_checkout_grace_minutes,
    }


def get_followup_validity_days(hospital_id: int) -> int:
    """The one value flows/booking/types/followup.py actually reads at the
    point of use -- falls back to DEFAULT_FOLLOWUP_VALIDITY_DAYS on a NULL
    (never configured) setting, same "nullable column, code-level default"
    convention hospitals.session_timeout_minutes already uses."""
    return get_hospital_settings(hospital_id)["followup_validity_days"] or DEFAULT_FOLLOWUP_VALIDITY_DAYS


def get_future_booking_days(hospital_id: int) -> int:
    """The one value connectors/tier1.py's self-healing slot top-up and every
    generate_slots_for_*() call site actually read -- falls back to
    DEFAULT_FUTURE_BOOKING_DAYS on a NULL (never configured) setting, same
    convention get_followup_validity_days() above uses."""
    return get_hospital_settings(hospital_id)["future_booking_days"] or DEFAULT_FUTURE_BOOKING_DAYS


def get_default_appointment_duration_minutes(hospital_id: int) -> int:
    """The one value db/repositories/doctors.py's compute_doctor_candidate_
    slots() actually reads, applied only to a doctor whose own
    slot_duration_minutes is NULL -- falls back to
    DEFAULT_APPOINTMENT_DURATION_MINUTES on a NULL (never configured)
    setting, same convention get_future_booking_days() above uses."""
    return (
        get_hospital_settings(hospital_id)["default_appointment_duration_minutes"]
        or DEFAULT_APPOINTMENT_DURATION_MINUTES
    )


def get_buffer_minutes(hospital_id: int) -> int:
    """The gap compute_doctor_candidate_slots() adds between every
    consecutive candidate slot, for every doctor at this hospital --
    falls back to DEFAULT_BUFFER_MINUTES (0, no gap) on a NULL (never
    configured) setting."""
    return get_hospital_settings(hospital_id)["buffer_minutes"] or DEFAULT_BUFFER_MINUTES


def get_max_appointments_per_day(hospital_id: int) -> int | None:
    """Unlike the two getters above, no code-level default to fall back to
    -- NULL genuinely means "no hospital-wide cap," the same as today
    before this setting existed. db/repositories/appointments.py's
    create_appointment() is the one enforcement point."""
    return get_hospital_settings(hospital_id)["max_appointments_per_day"]


def get_attendance_allowed_radius_meters(hospital_id: int) -> int:
    """The distance (meters) check_in()/check_out() (db/repositories/
    attendance.py) allow between a staff member's reported GPS position and
    attendance_latitude/longitude -- falls back to
    DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS on a NULL (never configured)
    setting, same convention get_buffer_minutes() above uses."""
    return (
        get_hospital_settings(hospital_id)["attendance_allowed_radius_meters"]
        or DEFAULT_ATTENDANCE_ALLOWED_RADIUS_METERS
    )


def get_attendance_early_checkin_minutes(hospital_id: int) -> int:
    """Minutes before attendance_shift_start a check-in is allowed --
    falls back to DEFAULT_ATTENDANCE_EARLY_CHECKIN_MINUTES on NULL."""
    return (
        get_hospital_settings(hospital_id)["attendance_early_checkin_minutes"]
        or DEFAULT_ATTENDANCE_EARLY_CHECKIN_MINUTES
    )


def get_attendance_late_threshold_minutes(hospital_id: int) -> int:
    """Minutes after attendance_shift_start before a check-in is marked
    late -- falls back to DEFAULT_ATTENDANCE_LATE_THRESHOLD_MINUTES on
    NULL."""
    return (
        get_hospital_settings(hospital_id)["attendance_late_threshold_minutes"]
        or DEFAULT_ATTENDANCE_LATE_THRESHOLD_MINUTES
    )


def update_hospital_settings(
    hospital_id: int, followup_validity_days: int | None, followup_fee: float | None,
    new_consultation_fee: float | None, home_collection_charge: float | None = None,
    future_booking_days: int | None = None, default_appointment_duration_minutes: int | None = None,
    buffer_minutes: int | None = None, max_appointments_per_day: int | None = None,
    attendance_latitude: float | None = None, attendance_longitude: float | None = None,
    attendance_allowed_radius_meters: int | None = None, attendance_allowed_ip_cidrs: str | None = None,
    attendance_shift_start: str | None = None, attendance_shift_end: str | None = None,
    attendance_early_checkin_minutes: int | None = None, attendance_late_threshold_minutes: int | None = None,
    attendance_auto_checkout_grace_minutes: int | None = None,
) -> dict:
    """portal/routes/settings.py's own write path -- always a full-object
    save (like every other settings form in this codebase), not a partial
    patch. Bounds validation (followup_validity_days > 0, fees >= 0) is the
    route layer's job (a clean 400), same discipline session_timeout_minutes'
    own portal route already follows -- this function trusts its caller and
    lets the DB's own CHECK constraints be the last line of defense."""
    session = get_session()
    session.execute(
        pg_insert(HospitalSettings)
        .values(
            hospital_id=hospital_id, followup_validity_days=followup_validity_days,
            followup_fee=followup_fee, new_consultation_fee=new_consultation_fee,
            home_collection_charge=home_collection_charge, future_booking_days=future_booking_days,
            default_appointment_duration_minutes=default_appointment_duration_minutes,
            buffer_minutes=buffer_minutes, max_appointments_per_day=max_appointments_per_day,
            attendance_latitude=attendance_latitude, attendance_longitude=attendance_longitude,
            attendance_allowed_radius_meters=attendance_allowed_radius_meters,
            attendance_allowed_ip_cidrs=attendance_allowed_ip_cidrs,
            attendance_shift_start=attendance_shift_start, attendance_shift_end=attendance_shift_end,
            attendance_early_checkin_minutes=attendance_early_checkin_minutes,
            attendance_late_threshold_minutes=attendance_late_threshold_minutes,
            attendance_auto_checkout_grace_minutes=attendance_auto_checkout_grace_minutes,
        )
        .on_conflict_do_update(
            index_elements=["hospital_id"],
            set_={
                "followup_validity_days": followup_validity_days, "followup_fee": followup_fee,
                "new_consultation_fee": new_consultation_fee, "home_collection_charge": home_collection_charge,
                "future_booking_days": future_booking_days,
                "default_appointment_duration_minutes": default_appointment_duration_minutes,
                "buffer_minutes": buffer_minutes, "max_appointments_per_day": max_appointments_per_day,
                "attendance_latitude": attendance_latitude, "attendance_longitude": attendance_longitude,
                "attendance_allowed_radius_meters": attendance_allowed_radius_meters,
                "attendance_allowed_ip_cidrs": attendance_allowed_ip_cidrs,
                "attendance_shift_start": attendance_shift_start, "attendance_shift_end": attendance_shift_end,
                "attendance_early_checkin_minutes": attendance_early_checkin_minutes,
                "attendance_late_threshold_minutes": attendance_late_threshold_minutes,
                "attendance_auto_checkout_grace_minutes": attendance_auto_checkout_grace_minutes,
            },
        )
    )
    session.commit()
    return get_hospital_settings(hospital_id)
