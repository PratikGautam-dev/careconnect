# db/repositories/dashboard.py
"""Staff dashboard aggregate stats (SPEC Section 12.8) -- portal/routes/dashboard.py's
/api/portal/dashboard. Split out of db/repository.py -- see
ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from db.connection import get_session
from db.models import STATUS_BOOKED, STATUS_CANCELLED, STATUS_RESCHEDULED
from db.orm_models import AppointmentRow, Department, DoctorRow

# --- Staff dashboard (SPEC Section 12.8) -- portal.py's /portal/dashboard.
# Every query here is hospital_id-scoped, same discipline as everywhere else
# in this file; the isolation test that matters is at the HTTP layer
# (tests/test_portal_dashboard.py), not repeated per-function here. ---

def get_dashboard_stats(hospital_id: int, now: datetime | None = None) -> dict:
    """The four "today"-scoped stat tiles (today's appointments, confirmed
    today, new patients today, no-shows today) plus a week-over-week % change
    for each, comparing today against the SAME WEEKDAY exactly 7 days ago --
    picked over a rolling-7-day-average comparison because it's the simplest
    comparison that's still apples-to-apples (a Monday against last Monday,
    not "today" against a blended mix of arbitrary weekdays), and needs only
    a single extra date offset, not a second aggregate shape. Also returns a
    fifth, non-"today"-scoped `upcoming_appointments` count -- see its own
    comment below for why.

    Definitions (all hospital_id + date-scoped):
    - "today's appointments": every appointment (any status) with
      scheduled_at falling on the date in question.
    - "confirmed today": of those, the ones still status='booked' (i.e. not
      cancelled) -- "confirmed" reads most naturally as "still on," not "has
      been formally re-confirmed" (no such action exists in this app).
    - "new patients today": distinct phone numbers whose EARLIEST appointment
      ever at this hospital (by created_at) was created on the date in
      question -- there's no separate patients table, so "new" is derived
      from first-appearance-in-appointments.
    - "no-shows today": still status='booked' appointments whose scheduled_at
      has already passed as of `now` (or, for last week's comparison day,
      the whole day, since it's entirely in the past). KNOWN LIMITATION: this
      app has no "attended"/"completed" status, so this is a heuristic, not a
      true no-show flag -- a booked appointment the patient actually attended
      looks identical to one they skipped once its time has passed. Flagged
      here deliberately rather than silently treated as exact.

    A week-over-week % change with a zero baseline (nothing happened on the
    comparison day) returns None (not a divide-by-zero, not a misleading
    "+100%") -- the caller/template shows "—" for that case.
    """
    now = now or datetime.now()
    today = now.date()
    last_week_day = today - timedelta(days=7)
    session = get_session()

    def _stats_for_day(day, no_show_cutoff: datetime) -> dict:
        day_start = datetime.combine(day, datetime.min.time()).isoformat()
        day_end = datetime.combine(day, datetime.max.time()).isoformat()
        A = AppointmentRow
        total = session.execute(
            select(func.count()).select_from(A)
            .where(A.hospital_id == hospital_id, A.scheduled_at >= day_start, A.scheduled_at <= day_end)
        ).scalar_one()
        confirmed = session.execute(
            select(func.count()).select_from(A)
            .where(A.hospital_id == hospital_id, A.scheduled_at >= day_start, A.scheduled_at <= day_end,
                   A.status == STATUS_BOOKED)
        ).scalar_one()
        A2 = aliased(AppointmentRow)
        exists_earlier = (
            select(1).select_from(A2)
            .where(A2.hospital_id == A.hospital_id, A2.phone == A.phone, A2.created_at < day_start)
            .correlate(A)
            .exists()
        )
        new_patients = session.execute(
            select(func.count(func.distinct(A.phone))).select_from(A)
            .where(A.hospital_id == hospital_id, A.created_at >= day_start, A.created_at <= day_end,
                   ~exists_earlier)
        ).scalar_one()
        no_shows = session.execute(
            select(func.count()).select_from(A)
            .where(A.hospital_id == hospital_id, A.scheduled_at >= day_start, A.scheduled_at <= day_end,
                   A.scheduled_at < no_show_cutoff.isoformat(), A.status == STATUS_BOOKED)
        ).scalar_one()
        return {"total": total, "confirmed": confirmed, "new_patients": new_patients, "no_shows": no_shows}

    today_stats = _stats_for_day(today, now)
    last_week_stats = _stats_for_day(last_week_day, datetime.combine(last_week_day, datetime.max.time()))

    def _delta_pct(today_v: int, last_week_v: int) -> float | None:
        if last_week_v == 0:
            return None
        return round((today_v - last_week_v) / last_week_v * 100, 1)

    upcoming_count = session.execute(
        select(func.count()).select_from(AppointmentRow)
        .where(AppointmentRow.hospital_id == hospital_id, AppointmentRow.scheduled_at > now.isoformat(),
               AppointmentRow.status == STATUS_BOOKED)
    ).scalar_one()

    return {
        "today_appointments": today_stats["total"],
        "today_appointments_delta_pct": _delta_pct(today_stats["total"], last_week_stats["total"]),
        "confirmed_today": today_stats["confirmed"],
        "confirmed_today_delta_pct": _delta_pct(today_stats["confirmed"], last_week_stats["confirmed"]),
        "new_patients_today": today_stats["new_patients"],
        "new_patients_today_delta_pct": _delta_pct(today_stats["new_patients"], last_week_stats["new_patients"]),
        "no_shows_today": today_stats["no_shows"],
        "no_shows_today_delta_pct": _delta_pct(today_stats["no_shows"], last_week_stats["no_shows"]),
        # Deliberately NOT "today"-scoped, unlike every stat above -- a
        # hospital's very first booking is very unlikely to land on today's
        # date specifically, and a dashboard reading all-zeros right after a
        # real booking just came in reads as broken. No delta_pct: a plain
        # forward-looking count, not a daily rate, so a week-over-week
        # comparison doesn't mean the same thing here.
        "upcoming_appointments": upcoming_count,
    }


def get_weekly_appointment_counts(hospital_id: int, now: datetime | None = None) -> list[dict]:
    """One point per day for the last 7 calendar days (today inclusive,
    oldest first) -- counts by scheduled_at (any status), consistent with
    get_dashboard_stats()'s own "today's appointments" definition (appointment
    VOLUME by day), not by created_at (which would be a booking-activity
    trend instead -- a legitimate alternative, but this keeps every dashboard
    number reading the same way)."""
    now = now or datetime.now()
    today = now.date()
    session = get_session()
    results = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time()).isoformat()
        day_end = datetime.combine(day, datetime.max.time()).isoformat()
        count = session.execute(
            select(func.count()).select_from(AppointmentRow)
            .where(AppointmentRow.hospital_id == hospital_id, AppointmentRow.scheduled_at >= day_start,
                   AppointmentRow.scheduled_at <= day_end)
        ).scalar_one()
        results.append({"date": day.isoformat(), "label": day.strftime("%a"), "count": count})
    return results


def get_appointments_by_department(hospital_id: int, days: int = 30, now: datetime | None = None) -> list[dict]:
    """Department share of appointment volume over a rolling **±`days`-day**
    window centered on now (default 30 days back AND 30 days forward) --
    ordered by count descending so the donut/legend both read
    largest-share-first. Deliberately NOT a past-only window (that was the
    original behavior): a hospital's very first booking is almost always for
    a FUTURE slot, and a past-only window left this donut empty immediately
    after a real booking came in, right when a staff member would most want
    to see it reflected."""
    now = now or datetime.now()
    window_start = datetime.combine(now.date() - timedelta(days=days - 1), datetime.min.time())
    window_end = datetime.combine(now.date() + timedelta(days=days), datetime.max.time())
    session = get_session()
    rows = session.execute(
        select(Department.name.label("department_name"), func.count().label("c"))
        .select_from(AppointmentRow)
        .join(Department, Department.id == AppointmentRow.department_id)
        .where(AppointmentRow.hospital_id == hospital_id, AppointmentRow.scheduled_at >= window_start.isoformat(),
               AppointmentRow.scheduled_at <= window_end.isoformat())
        .group_by(Department.name)
        .order_by(func.count().desc())
    ).all()
    return [{"department_name": r.department_name, "count": r.c} for r in rows]


def get_recent_activity_feed(hospital_id: int, limit: int = 10) -> list[dict]:
    """A lightweight "what just happened" feed built entirely from
    appointments' own status/timestamps -- SPEC Section 12.8 looked for an
    existing WhatsApp message log to reuse and found none exists (nothing in
    this build persists inbound/outbound message text, only conversation
    STATE via core/session_store.py's session store); appointment status changes
    are the smallest real substitute already captured, so this reuses those
    rather than adding new message logging.

    Each row contributes exactly ONE event based on its CURRENT status: a
    still-'booked' row's event is "Booked appointment" at created_at; a
    cancelled/rescheduled row's event uses updated_at (the column
    cancel_appointment()/mark_rescheduled() now stamp specifically for this)
    so it shows the time the status actually changed, not the original
    booking time. A reschedule legitimately produces two feed entries over
    time -- the OLD row's "Rescheduled appointment" and the NEW row's own
    later "Booked appointment" -- which is correct, not a double-count: two
    real, separately-timed things happened."""
    session = get_session()
    order_col = func.coalesce(AppointmentRow.updated_at, AppointmentRow.created_at)
    rows = session.execute(
        select(
            AppointmentRow.status, AppointmentRow.phone, DoctorRow.name.label("doctor_name"),
            Department.name.label("department_name"), AppointmentRow.created_at, AppointmentRow.updated_at,
        )
        .select_from(AppointmentRow)
        .join(Department, Department.id == AppointmentRow.department_id)
        .join(DoctorRow, DoctorRow.id == AppointmentRow.doctor_id)
        .where(AppointmentRow.hospital_id == hospital_id)
        .order_by(order_col.desc())
        .limit(limit)
    ).all()
    labels = {
        STATUS_BOOKED: "Booked appointment",
        STATUS_CANCELLED: "Cancelled appointment",
        STATUS_RESCHEDULED: "Rescheduled appointment",
    }
    feed = []
    for r in rows:
        event_at = r.updated_at or r.created_at
        feed.append({
            "label": labels.get(r.status, r.status),
            "phone": r.phone,
            "doctor_name": r.doctor_name,
            "department_name": r.department_name,
            "at": datetime.fromisoformat(event_at),
        })
    return feed


