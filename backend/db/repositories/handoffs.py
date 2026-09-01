# db/repositories/handoffs.py
"""Human handoff queue -- fed by flows.py's reception_handoff feature and
core/main.py's unexpected-exception catch. Split out of db/repository.py --
see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import date, datetime, timedelta, timezone
from typing import cast

from sqlalchemy import insert, select, update
from sqlalchemy.engine import CursorResult

from db.connection import get_session
from db.orm_models import HandoffMessage, HandoffRequest

# Messages page follow-up: an open handoff with no new activity from either
# side for this many hours auto-resolves (see auto_resolve_stale_handoffs()
# below) unless a hospital has its own hospitals.handoff_auto_resolve_hours
# set. Same "nullable column + code-level default" shape as
# session_timeout_minutes's own 30-minute fallback.
DEFAULT_HANDOFF_AUTO_RESOLVE_HOURS = 24

# Sentinel written to handoff_requests.resolved_by when the scheduler (not a
# staff member) resolves a handoff -- distinguishes it from a real staff
# session's hashed token (portal/deps.py's _session_id(), the same value
# patient_visit_notes.created_by_session_id already uses), so the Messages
# page can tell "staff actually handled this" from "it just timed out."
AUTO_RESOLVED_BY = "auto"

# --- Human handoff queue -- fed by flows.py's reception_handoff feature and
# core/main.py's unexpected-exception catch (see db/schema.sql's own comment
# on handoff_requests for why these two unrelated triggers share one table). ---

def create_handoff_request(hospital_id: int, phone: str, reason: str, message_text: str | None = None) -> dict:
    """Two-way threading follow-up (Spec.md Section 0): the trigger message
    is now ALSO inserted as the thread's first inbound handoff_messages row
    -- get_handoff_messages() is the single source of truth for the portal's
    chat thread, not a mix of this row's own message_text plus the table."""
    session = get_session()
    row = session.execute(
        insert(HandoffRequest)
        .values(hospital_id=hospital_id, phone=phone, reason=reason, message_text=message_text)
        .returning(HandoffRequest.id, HandoffRequest.created_at)
    ).first()
    assert row is not None  # INSERT ... RETURNING always returns the inserted row
    if message_text:
        session.execute(
            insert(HandoffMessage).values(
                hospital_id=hospital_id, handoff_request_id=row.id,
                direction="inbound", message_text=message_text,
            )
        )
    session.commit()
    return {
        "id": row.id, "hospital_id": hospital_id, "phone": phone, "reason": reason,
        "message_text": message_text, "status": "open", "created_at": row.created_at, "resolved_at": None,
    }


def get_handoff_requests(
    hospital_id: int, status: str | None = "open", limit: int = 100, date_str: str | None = None,
    reason: str | None = None,
) -> list[dict]:
    """status=None returns every request regardless of state (for a staff
    member reviewing history); the default "open" is the actual work queue.
    Item 6 (Spec.md Section 0): date_str ("YYYY-MM-DD"), when given, scopes
    to requests created on that one calendar day. Item 3: soft-deleted
    requests (deleted_at IS NOT NULL) are always excluded, same convention
    _APPOINTMENT_SELECT enforces for appointments.

    Messages page follow-up: reason ("patient_requested"/"system_error"),
    when given, scopes to just that trigger -- the Messages page's "Errored"
    tab passes reason="system_error" with status=None (any status, not just
    open) so a staff member can still see a bot error that's already been
    resolved, not just currently-open ones."""
    session = get_session()
    stmt = select(
        HandoffRequest.id, HandoffRequest.phone, HandoffRequest.reason, HandoffRequest.message_text,
        HandoffRequest.status, HandoffRequest.created_at, HandoffRequest.resolved_at,
        HandoffRequest.resolved_by,
    ).where(HandoffRequest.hospital_id == hospital_id, HandoffRequest.deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(HandoffRequest.status == status)
    if reason is not None:
        stmt = stmt.where(HandoffRequest.reason == reason)
    if date_str:
        # created_at is stamped by Postgres's own `now()::text` default
        # (space-separated, "YYYY-MM-DD HH:MM:SS.ffffff+TZ" -- NOT the
        # "T"-separated ISO format datetime.isoformat() produces elsewhere in
        # this file), so the boundaries here must match THAT shape, not
        # reuse the T-separated pattern appointments.scheduled_at uses.
        # Exclusive next-day upper bound sidesteps any further precision
        # mismatch at the boundary itself.
        next_day = (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()
        stmt = stmt.where(
            HandoffRequest.created_at >= f"{date_str} 00:00:00",
            HandoffRequest.created_at < f"{next_day} 00:00:00",
        )
    stmt = stmt.order_by(HandoffRequest.created_at.desc()).limit(limit)
    rows = session.execute(stmt).all()
    return [dict(r._mapping) for r in rows]


# "Bot stuck on Talk to Reception" follow-up (Spec.md Section 0): an open
# handoff previously silenced the bot for that phone INDEFINITELY -- no
# staleness bound at all, so a request staff forgot to resolve (or took
# hours to get to) left the patient with no way back into the bot, not even
# the reset-keyword escape hatch (deliberately suppressed for a genuinely
# ACTIVE handoff, per the earlier explicit request). Deliberately a fixed,
# generous window independent of the hospital's own (often much shorter,
# e.g. 2-5 minute) session_timeout_minutes -- that setting governs ordinary
# bot-conversation inactivity, not how long a real human is reasonably given
# to answer an escalation; conflating the two would make a 2-minute bot
# timeout also cut off a legitimate reception request after 2 minutes of
# silence, which is a completely different (unwanted) behavior.
_HANDOFF_STALE_MINUTES = 60


def has_open_handoff(hospital_id: int, phone: str) -> bool:
    """Item 7 (Spec.md Section 0): checked at the very top of flows.py's
    router, before any bot logic (including the reset-keyword escape hatch)
    runs -- once a patient is in an active handoff, the bot must go
    completely silent for that phone, not just skip its own menu."""
    return get_open_handoff(hospital_id, phone) is not None


def get_open_handoff(hospital_id: int, phone: str, now: datetime | None = None) -> dict | None:
    """Two-way threading follow-up: like has_open_handoff() above, but
    returns the row (specifically its id) so flows.py can actually record
    the patient's message against it, not just know one exists.

    "Bot stuck on Talk to Reception" follow-up: a row older than
    _HANDOFF_STALE_MINUTES is treated as if it weren't open anymore FOR
    THIS PURPOSE -- the bot resumes normal service -- but its `status` in
    the DB is left completely untouched (still 'open'), so staff still see
    it in the portal queue and can resolve it whenever they actually get to
    it; this only stops it from silencing the bot forever."""
    session = get_session()
    # created_at is stamped by Postgres's own `now()::text` default, which is
    # UTC (space-separated -- see get_handoff_requests()'s own date-filter fix
    # for the same format mismatch this mirrors) -- so the threshold must be
    # computed in UTC too, not local time, or a fresh row can already look
    # "stale" purely from the client/server clock offset.
    now = now or datetime.now(timezone.utc)
    threshold = (now - timedelta(minutes=_HANDOFF_STALE_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    row = session.execute(
        select(HandoffRequest.id, HandoffRequest.phone, HandoffRequest.reason, HandoffRequest.status, HandoffRequest.created_at)
        .where(
            HandoffRequest.hospital_id == hospital_id, HandoffRequest.phone == phone,
            HandoffRequest.status == "open", HandoffRequest.deleted_at.is_(None),
            HandoffRequest.created_at >= threshold,
        )
        .limit(1)
    ).first()
    return dict(row._mapping) if row else None


def add_handoff_message(hospital_id: int, handoff_request_id: int, direction: str, message_text: str) -> dict:
    """direction: 'inbound' (patient -> staff, recorded by flows.py while a
    handoff is open) or 'outbound' (staff -> patient, recorded by
    portal_reply_handoff() after the real WhatsApp send succeeds)."""
    session = get_session()
    row = session.execute(
        insert(HandoffMessage)
        .values(
            hospital_id=hospital_id, handoff_request_id=handoff_request_id,
            direction=direction, message_text=message_text,
        )
        .returning(HandoffMessage.id, HandoffMessage.created_at)
    ).first()
    assert row is not None  # INSERT ... RETURNING always returns the inserted row
    session.commit()
    return {
        "id": row.id, "handoff_request_id": handoff_request_id, "direction": direction,
        "message_text": message_text, "created_at": row.created_at,
    }


def get_handoff_messages(hospital_id: int, handoff_request_id: int) -> list[dict]:
    """The full thread for one handoff, oldest first -- single source of
    truth for the portal's chat-thread UI (create_handoff_request() inserts
    the trigger message here too, so callers never need to separately show
    handoff_requests.message_text)."""
    session = get_session()
    rows = session.execute(
        select(HandoffMessage.id, HandoffMessage.direction, HandoffMessage.message_text, HandoffMessage.created_at)
        .where(HandoffMessage.hospital_id == hospital_id, HandoffMessage.handoff_request_id == handoff_request_id)
        .order_by(HandoffMessage.created_at.asc(), HandoffMessage.id.asc())
    ).all()
    return [dict(r._mapping) for r in rows]


def resolve_handoff_request(hospital_id: int, handoff_id: int, resolved_by: str | None = None) -> bool:
    """resolved_by: the resolving staff member's hashed session token
    (portal/deps.py's _session_id()), or AUTO_RESOLVED_BY for the scheduler
    (auto_resolve_stale_handoffs() below) -- distinguishes a real staff
    resolution from an unattended timeout. Defaults to None only for
    backward compatibility with any not-yet-updated caller; every real call
    site (portal_resolve_handoff(), the auto-resolve job) passes one
    explicitly."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(HandoffRequest)
        .where(HandoffRequest.id == handoff_id, HandoffRequest.hospital_id == hospital_id, HandoffRequest.status == "open")
        .values(status="resolved", resolved_at=datetime.now().isoformat(), resolved_by=resolved_by)
    ))
    session.commit()
    return result.rowcount > 0


def bulk_resolve_handoff_requests(hospital_id: int, handoff_ids: list[int], resolved_by: str) -> list[int]:
    """Messages page bulk action -- resolves every id in `handoff_ids` that
    actually belongs to this hospital and is currently open, silently
    ignoring the rest (a stale id from a page that hasn't refreshed, an id
    belonging to another hospital, an already-resolved one) rather than
    erroring the whole batch over one bad id. Returns the ids actually
    resolved, so the caller can report exactly what happened."""
    if not handoff_ids:
        return []
    session = get_session()
    rows = session.execute(
        update(HandoffRequest)
        .where(
            HandoffRequest.id.in_(handoff_ids), HandoffRequest.hospital_id == hospital_id,
            HandoffRequest.status == "open",
        )
        .values(status="resolved", resolved_at=datetime.now().isoformat(), resolved_by=resolved_by)
        .returning(HandoffRequest.id)
    ).all()
    session.commit()
    return [r[0] for r in rows]


def bulk_soft_delete_handoffs(hospital_id: int, handoff_ids: list[int]) -> list[int]:
    """Messages page bulk action -- same hospital-scoped, ignore-the-rest
    semantics as bulk_resolve_handoff_requests() above. Soft-delete only
    (deleted_at set), matching soft_delete_handoff()'s own established
    convention -- no status restriction, same reasoning that function's own
    docstring already gives."""
    if not handoff_ids:
        return []
    session = get_session()
    rows = session.execute(
        update(HandoffRequest)
        .where(
            HandoffRequest.id.in_(handoff_ids), HandoffRequest.hospital_id == hospital_id,
            HandoffRequest.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now().isoformat())
        .returning(HandoffRequest.id)
    ).all()
    session.commit()
    return [r[0] for r in rows]


def auto_resolve_stale_handoffs(hospital_id: int, threshold_hours: int, now: datetime | None = None) -> list[int]:
    """Messages page follow-up: auto-resolves every OPEN handoff at this
    hospital whose thread has had no activity (from either side) in the
    last `threshold_hours` -- called per-hospital by
    /internal/auto-resolve-handoffs (webhook/cron_routes.py), same external-
    cron-triggered pattern as send_reminders()/top_up_slots_for_hospital().

    "No activity" is judged by the THREAD (handoff_messages), not
    handoff_requests.created_at alone -- a patient or staff member replying
    keeps a handoff alive past its original creation time, and
    create_handoff_request() always inserts the trigger message as the
    thread's first row, so every handoff has at least one handoff_messages
    row to check against; there's no separate "never had any messages" edge
    case to handle. A NOT EXISTS (no message at or after the cutoff) is
    exactly "nothing happened recently enough," in one query rather than a
    separate MAX(created_at) aggregation per handoff.

    resolved_by is stamped AUTO_RESOLVED_BY, never a staff session id, so
    the Messages page/dashboard can always tell an auto-resolve apart from
    a real staff member's action. Returns the ids actually resolved."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=threshold_hours)).strftime("%Y-%m-%d %H:%M:%S")
    session = get_session()
    stale_ids = [
        row[0] for row in session.execute(
            select(HandoffRequest.id).where(
                HandoffRequest.hospital_id == hospital_id, HandoffRequest.status == "open",
                HandoffRequest.deleted_at.is_(None), HandoffRequest.created_at < cutoff,
                ~select(HandoffMessage.id).where(
                    HandoffMessage.handoff_request_id == HandoffRequest.id,
                    HandoffMessage.created_at >= cutoff,
                ).exists(),
            )
        ).all()
    ]
    if not stale_ids:
        return []
    resolved_at = datetime.now().isoformat()
    session.execute(
        update(HandoffRequest)
        .where(HandoffRequest.id.in_(stale_ids))
        .values(status="resolved", resolved_at=resolved_at, resolved_by=AUTO_RESOLVED_BY)
    )
    session.commit()
    return stale_ids


def soft_delete_handoff(hospital_id: int, handoff_id: int) -> bool:
    """Item 3: same soft-delete convention as soft_delete_appointment() --
    no restriction on status here (unlike appointments' "must be resolved
    first" guard) since an open handoff has no in-progress side effect a
    delete could silently orphan -- staff can delete a stale/mistaken
    request directly."""
    session = get_session()
    result = cast(CursorResult, session.execute(
        update(HandoffRequest)
        .where(HandoffRequest.id == handoff_id, HandoffRequest.hospital_id == hospital_id, HandoffRequest.deleted_at.is_(None))
        .values(deleted_at=datetime.now().isoformat())
    ))
    session.commit()
    return result.rowcount > 0

