# db/repositories/handoffs.py
"""Human handoff queue -- fed by flows.py's reception_handoff feature and
core/main.py's unexpected-exception catch. Split out of db/repository.py --
see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import date, datetime, timedelta

from db.connection import get_connection

# --- Human handoff queue -- fed by flows.py's reception_handoff feature and
# core/main.py's unexpected-exception catch (see db/schema.sql's own comment
# on handoff_requests for why these two unrelated triggers share one table). ---

def create_handoff_request(hospital_id: int, phone: str, reason: str, message_text: str | None = None) -> dict:
    """Two-way threading follow-up (Spec.md Section 0): the trigger message
    is now ALSO inserted as the thread's first inbound handoff_messages row
    -- get_handoff_messages() is the single source of truth for the portal's
    chat thread, not a mix of this row's own message_text plus the table."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO handoff_requests (hospital_id, phone, reason, message_text) "
        "VALUES (?, ?, ?, ?) RETURNING id, created_at",
        (hospital_id, phone, reason, message_text),
    )
    row = cur.fetchone()
    if message_text:
        conn.execute(
            "INSERT INTO handoff_messages (hospital_id, handoff_request_id, direction, message_text) "
            "VALUES (?, ?, 'inbound', ?)",
            (hospital_id, row["id"], message_text),
        )
    conn.commit()
    return {
        "id": row["id"], "hospital_id": hospital_id, "phone": phone, "reason": reason,
        "message_text": message_text, "status": "open", "created_at": row["created_at"], "resolved_at": None,
    }


def get_handoff_requests(
    hospital_id: int, status: str | None = "open", limit: int = 100, date_str: str | None = None,
) -> list[dict]:
    """status=None returns every request regardless of state (for a staff
    member reviewing history); the default "open" is the actual work queue.
    Item 6 (Spec.md Section 0): date_str ("YYYY-MM-DD"), when given, scopes
    to requests created on that one calendar day. Item 3: soft-deleted
    requests (deleted_at IS NOT NULL) are always excluded, same convention
    _APPOINTMENT_SELECT enforces for appointments."""
    conn = get_connection()
    conditions = ["hospital_id = ?", "deleted_at IS NULL"]
    params: list = [hospital_id]
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if date_str:
        # created_at is stamped by Postgres's own `now()::text` default
        # (space-separated, "YYYY-MM-DD HH:MM:SS.ffffff+TZ" -- NOT the
        # "T"-separated ISO format datetime.isoformat() produces elsewhere in
        # this file), so the boundaries here must match THAT shape, not
        # reuse the T-separated pattern appointments.scheduled_at uses.
        # Exclusive next-day upper bound sidesteps any further precision
        # mismatch at the boundary itself.
        next_day = (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()
        conditions.append("created_at >= ? AND created_at < ?")
        params.extend([f"{date_str} 00:00:00", f"{next_day} 00:00:00"])
    params.append(limit)
    rows = conn.execute(
        "SELECT id, phone, reason, message_text, status, created_at, resolved_at FROM handoff_requests "
        f"WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT ?",
        tuple(params),
    ).fetchall()
    return [dict(r) for r in rows]


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
    conn = get_connection()
    now = now or datetime.now()
    # created_at is stamped by Postgres's own `now()::text` default (space-
    # separated -- see get_handoff_requests()'s own date-filter fix for the
    # same format mismatch this mirrors), so the threshold must match that
    # shape, not the "T"-separated isoformat() used elsewhere in this file.
    threshold = (now - timedelta(minutes=_HANDOFF_STALE_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        "SELECT id, phone, reason, status, created_at FROM handoff_requests "
        "WHERE hospital_id = ? AND phone = ? AND status = 'open' AND deleted_at IS NULL "
        "AND created_at >= ? LIMIT 1",
        (hospital_id, phone, threshold),
    ).fetchone()
    return dict(row) if row else None


def add_handoff_message(hospital_id: int, handoff_request_id: int, direction: str, message_text: str) -> dict:
    """direction: 'inbound' (patient -> staff, recorded by flows.py while a
    handoff is open) or 'outbound' (staff -> patient, recorded by
    portal_reply_handoff() after the real WhatsApp send succeeds)."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO handoff_messages (hospital_id, handoff_request_id, direction, message_text) "
        "VALUES (?, ?, ?, ?) RETURNING id, created_at",
        (hospital_id, handoff_request_id, direction, message_text),
    )
    row = cur.fetchone()
    conn.commit()
    return {
        "id": row["id"], "handoff_request_id": handoff_request_id, "direction": direction,
        "message_text": message_text, "created_at": row["created_at"],
    }


def get_handoff_messages(hospital_id: int, handoff_request_id: int) -> list[dict]:
    """The full thread for one handoff, oldest first -- single source of
    truth for the portal's chat-thread UI (create_handoff_request() inserts
    the trigger message here too, so callers never need to separately show
    handoff_requests.message_text)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, direction, message_text, created_at FROM handoff_messages "
        "WHERE hospital_id = ? AND handoff_request_id = ? ORDER BY created_at ASC, id ASC",
        (hospital_id, handoff_request_id),
    ).fetchall()
    return [dict(r) for r in rows]


def resolve_handoff_request(hospital_id: int, handoff_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE handoff_requests SET status = 'resolved', resolved_at = ? WHERE id = ? AND hospital_id = ? AND status = 'open'",
        (datetime.now().isoformat(), handoff_id, hospital_id),
    )
    conn.commit()
    return cur.rowcount > 0


def soft_delete_handoff(hospital_id: int, handoff_id: int) -> bool:
    """Item 3: same soft-delete convention as soft_delete_appointment() --
    no restriction on status here (unlike appointments' "must be resolved
    first" guard) since an open handoff has no in-progress side effect a
    delete could silently orphan -- staff can delete a stale/mistaken
    request directly."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE handoff_requests SET deleted_at = ? WHERE id = ? AND hospital_id = ? AND deleted_at IS NULL",
        (datetime.now().isoformat(), handoff_id, hospital_id),
    )
    conn.commit()
    return cur.rowcount > 0

