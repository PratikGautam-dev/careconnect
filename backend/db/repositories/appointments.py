# db/repositories/appointments.py
"""Appointment booking, cancellation, rescheduling, and lookups -- the core
booking data path both the WhatsApp flow and the staff portal go through.
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from datetime import datetime, timedelta

from db.connection import IntegrityError, get_connection
from db.models import (
    Appointment, DuplicateBookingError, QuotaExceededError,
    SOURCE_WHATSAPP, STATUS_ATTENDED, STATUS_BOOKED, STATUS_CANCELLED, STATUS_NO_SHOW, STATUS_RESCHEDULED,
    _APPOINTMENT_SELECT, _generate_patient_display_id, _generate_reference_id, _row_to_appointment,
)

# --- Appointments ---

def _upsert_patient(conn, hospital_id: int, phone: str, name: str | None, age: int | None = None) -> dict:
    """Section 12.9: keeps `patients` in sync on every booking, both sources.
    COALESCE(EXCLUDED.name, patients.name) means a name, when given (staff
    bookings, or as of Section 12.11 a WhatsApp patient asked for the first
    time), always wins and fills in/overwrites; when not given (a repeat
    WhatsApp patient who's already on file, so booking_flow.py skips asking
    again), an existing name/age is never clobbered back to NULL. Same
    COALESCE treatment for `age` -- Section 12.11's WhatsApp-collected field,
    independent of the staff portal's date_of_birth (Section 12.10).

    Item 8 (Spec.md Section 0): now returns {id, name, age} -- called BEFORE
    the appointments INSERT (moved up from after, same transaction either
    way) so create_appointment() can denormalize the RESOLVED id/name (the
    COALESCE result, not just whatever was passed in this call) onto the new
    appointments row.

    Patient identity system (Spec.md Section 0): also generates and returns
    patient_display_id, but ONLY the first time a `patients` row is created
    for this (hospital_id, phone).

    Patient identity SEPARATION (Spec.md Section 0) dropped patients'
    UNIQUE(hospital_id, phone) constraint (multiple profiles per phone are
    now allowed via patient_links), so the ON CONFLICT (hospital_id, phone)
    this used to use no longer has a matching unique index to target --
    replaced with an explicit lookup-then-update-or-insert, guarded by a
    Postgres SESSION-level advisory lock (not _xact_lock -- this function
    runs on the still-autocommitting connection, before create_appointment()
    opens its own explicit transaction, so there's no transaction for a
    _xact_lock to scope to; released explicitly in the finally block) scoped
    to (hospital_id, phone) so two concurrent bookings for a brand-new phone
    can't both see "no existing row" and insert two. When more than one
    `patients` row already exists for this phone (a multi-profile phone that
    still has a caller going through the phone-only path -- the staff
    portal, out of scope for patient_id this round), the OLDEST one (lowest
    id -- the original single-profile-per-phone row every such phone
    started with) is the one updated, preserving this function's original
    "one implicit profile per phone" behavior for every caller that doesn't
    pass patient_id."""
    conn.execute("SELECT pg_advisory_lock(hashtext(?))", (f"upsert_patient|{hospital_id}|{phone}",))
    try:
        existing = conn.execute(
            "SELECT id, name, age, patient_display_id FROM patients "
            "WHERE hospital_id = ? AND phone = ? ORDER BY id LIMIT 1",
            (hospital_id, phone),
        ).fetchone()
        if existing is not None:
            resolved_name = name if name is not None else existing["name"]
            resolved_age = age if age is not None else existing["age"]
            conn.execute(
                "UPDATE patients SET name = ?, age = ? WHERE id = ?",
                (resolved_name, resolved_age, existing["id"]),
            )
            return {
                "id": existing["id"], "name": resolved_name, "age": resolved_age,
                "patient_display_id": existing["patient_display_id"],
            }
        row = conn.execute(
            "INSERT INTO patients (hospital_id, phone, name, age) VALUES (?, ?, ?, ?) RETURNING id, name, age",
            (hospital_id, phone, name, age),
        ).fetchone()
        display_id = _generate_patient_display_id(conn, hospital_id)
        conn.execute("UPDATE patients SET patient_display_id = ? WHERE id = ?", (display_id, row["id"]))
        return {"id": row["id"], "name": row["name"], "age": row["age"], "patient_display_id": display_id}
    finally:
        conn.execute("SELECT pg_advisory_unlock(hashtext(?))", (f"upsert_patient|{hospital_id}|{phone}",))


def create_appointment(
    hospital_id: int,
    phone: str,
    department_id: str,
    doctor_id: str,
    scheduled_at: datetime,
    source: str = SOURCE_WHATSAPP,
    patient_name: str | None = None,
    patient_age: int | None = None,
    patient_id: int | None = None,
    exclude_appointment_id: int | None = None,
    appointment_type_id: str | None = None,
    consent_given_at: str | None = None,
) -> Appointment:
    """Raises db.connection.IntegrityError if this doctor's max_bookings_per_slot
    (default 1) worth of *booked* appointments already exist at this exact
    scheduled_at -- that's the actual double-booking guard, not application
    logic. Catching it gracefully is Phase 8 work, not done here. Raises the
    more specific QuotaExceededError (still an IntegrityError) if the
    doctor's daily_booking_limit or the requested source's online_quota/
    walkin_quota (Section 14.7, first enforced here as of Section 12.9) is
    exhausted for scheduled_at's date.

    `source` distinguishes a WhatsApp patient self-booking (the default --
    every pre-Section-12.9 call site keeps working completely unchanged) from
    a staff-created walk-in/phone booking ("staff", portal.py's
    /portal/new-booking) -- purely descriptive, never branched on for booking
    LOGIC beyond which quota column it counts against. `patient_name`/
    `patient_age` are supplied by the staff path (phone-upsert semantics,
    unchanged).

    Patient identity SEPARATION (Spec.md Section 0): `patient_id`, when given
    (the WhatsApp path, post-separation -- an ALREADY-selected/created
    `patients` row via `active_patient_id`), takes over identity resolution
    entirely -- `_upsert_patient()` is skipped, name/age are read directly off
    that row, and the duplicate-booking check below compares `patient_id`
    directly instead of the old name+age heuristic. `patient_id=None` (the
    staff portal, and any legacy caller) falls through to the exact original
    `_upsert_patient()`-by-phone behavior, byte-for-byte -- this parameter is
    purely additive.

    `exclude_appointment_id`, when given, is left out of BOTH duplicate-check
    branches below -- needed by reschedule (Tier1Connector.reschedule_booking()
    passes the OLD appointment's id here): that function books the NEW slot
    via this same create_appointment() BEFORE marking the old appointment
    rescheduled (so a losing race on the new slot leaves the patient's
    original appointment intact, see reschedule_booking()'s own docstring) --
    meaning the old appointment is still status='booked', for the same
    doctor, same patient_id, at the moment this duplicate check runs. Without
    excluding it, every reschedule would incorrectly self-block as "you
    already have an appointment with this doctor" against the very
    appointment being replaced.

    Concurrency (Section 12.9): daily_booking_limit/online_quota/walkin_quota
    are per-DOCTOR-configured values, not fixed schema constants, so unlike
    the OLD max_bookings_per_slot-only design (a plain UNIQUE index needed no
    lock at all) they can't be enforced as a static constraint. A Postgres
    advisory transaction lock scoped to (doctor_id, date) serializes every
    booking attempt -- staff AND WhatsApp alike -- for the same doctor on the
    same day, so the whole check-then-insert sequence below (quotas AND the
    per-slot ordinal assignment) is atomic against genuine concurrent
    requests, not just correct when called one at a time. The lock is
    released automatically on COMMIT/ROLLBACK (that's what "_xact_lock"
    means).

    Wrapped in a real BEGIN/ROLLBACK/COMMIT block (unlike every other
    function in this file, which relies on db/connection.py's
    autocommit=True) -- the `except BaseException` below is not optional:
    this is the ONE place in the app that opens a real multi-statement
    transaction on the single shared connection, and leaving it open after an
    unexpected error would poison every subsequent query on that connection
    (db/connection.py's own docstring explains exactly this failure mode,
    which is why autocommit=True was chosen everywhere else) -- so every exit
    path, expected or not, must ROLLBACK or COMMIT. This is also exactly why
    there's deliberately no retry-on-conflict inside this transaction (an
    earlier version had one, a leftover from before this lock existed): once
    ANY statement in an explicit Postgres transaction fails, the whole
    transaction is aborted and every FURTHER statement on it fails too, with
    "current transaction is aborted" (a different exception than whatever
    actually went wrong) until a ROLLBACK -- so "catch a failure and issue
    another statement to retry, inside the same transaction" doesn't just
    not-help here, it actively replaces a meaningful IntegrityError/
    QuotaExceededError with a useless, wrong-typed one that no caller's
    `except IntegrityError:` would catch. Confirmed live: forcing a genuine
    INSERT failure here and then issuing an unrelated query on the same
    connection afterward shows the connection recovers cleanly either way
    (see tests/test_create_appointment_transaction_safety.py) -- but ONLY
    the current code (no inner retry) also gets the exception TYPE right for
    the caller."""
    conn = get_connection()
    scheduled_at_iso = scheduled_at.isoformat()
    scheduled_date = scheduled_at.date()
    day_start = datetime.combine(scheduled_date, datetime.min.time()).isoformat()
    day_end = datetime.combine(scheduled_date, datetime.max.time()).isoformat()

    doctor_row = conn.execute(
        "SELECT max_bookings_per_slot, daily_booking_limit, online_quota, walkin_quota "
        "FROM doctors WHERE hospital_id = ? AND id = ?",
        (hospital_id, doctor_id),
    ).fetchone()
    max_bookings_per_slot = doctor_row["max_bookings_per_slot"] if doctor_row else 1
    daily_booking_limit = doctor_row["daily_booking_limit"] if doctor_row else None
    source_quota = None
    if doctor_row:
        source_quota = doctor_row["online_quota"] if source == SOURCE_WHATSAPP else doctor_row["walkin_quota"]

    # Name/age-asked-again regression fix (Spec.md Section 0): _upsert_patient()
    # used to run INSIDE the transaction below, right before the appointments
    # INSERT -- meaning a QuotaExceededError/DuplicateBookingError raised
    # earlier in that SAME transaction rolled the upsert back too (the whole
    # transaction is one atomic unit), so a patient whose very FIRST booking
    # attempt happened to hit either of those checks never got saved to
    # `patients` at all, and was incorrectly asked for name/age again on
    # their next (otherwise-successful) attempt. Running it here instead --
    # BEFORE "BEGIN", on the still-autocommitting connection -- makes it its
    # own independent, immediately-durable statement: the patient's name/age
    # are saved regardless of whether THIS booking attempt goes on to
    # succeed or fail. `patient["name"]`/`patient["age"]` are the resolved
    # COALESCE result (this attempt's value if given, otherwise whatever was
    # already on file) -- used directly below as this attempt's effective
    # name/age, replacing the old separate "read the pre-attempt profile"
    # query that used to run inside the transaction for the same purpose.
    #
    # Patient identity SEPARATION (Spec.md Section 0): when patient_id is
    # given, identity is already fully resolved (a specific linked patient
    # profile) -- read that row directly instead of upserting by phone (which
    # would be wrong now that multiple profiles can share one phone).
    if patient_id is not None:
        patient_row = conn.execute(
            "SELECT id, name, age FROM patients WHERE hospital_id = ? AND id = ?",
            (hospital_id, patient_id),
        ).fetchone()
        if patient_row is None:
            raise ValueError(f"patient_id {patient_id} not found for hospital {hospital_id}")
        patient = {"id": patient_row["id"], "name": patient_row["name"], "age": patient_row["age"]}
    else:
        patient = _upsert_patient(conn, hospital_id, phone, patient_name, patient_age)

    conn.execute("BEGIN")
    try:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(?))",
            (f"{doctor_id}|{scheduled_date.isoformat()}",),
        )

        if daily_booking_limit is not None:
            day_count = conn.execute(
                "SELECT COUNT(*) AS c FROM appointments WHERE hospital_id = ? AND doctor_id = ? "
                "AND scheduled_at >= ? AND scheduled_at <= ? AND status = ?",
                (hospital_id, doctor_id, day_start, day_end, STATUS_BOOKED),
            ).fetchone()["c"]
            if day_count >= daily_booking_limit:
                raise QuotaExceededError("This doctor has reached today's booking limit.")

        if source_quota is not None:
            source_count = conn.execute(
                "SELECT COUNT(*) AS c FROM appointments WHERE hospital_id = ? AND doctor_id = ? "
                "AND scheduled_at >= ? AND scheduled_at <= ? AND status = ? AND source = ?",
                (hospital_id, doctor_id, day_start, day_end, STATUS_BOOKED, source),
            ).fetchone()["c"]
            if source_count >= source_quota:
                kind = "Online booking" if source == SOURCE_WHATSAPP else "Walk-in"
                raise QuotaExceededError(f"{kind} quota full for this doctor today.")

        # The smallest booking_ordinal in [0, max_bookings_per_slot) NOT
        # already used by a currently-BOOKED row at this exact slot --
        # deliberately NOT a plain COUNT(*): a cancellation doesn't delete
        # its row or free its ordinal implicitly, so booked ordinals can have
        # gaps (book A -> ordinal 0, book B -> ordinal 1, cancel A, book C ->
        # COUNT(booked) is 1, but ordinal 1 is already B's -- COUNT(*) as the
        # ordinal would collide with B here, a real sequence, not a
        # contrived one). generate_series against the valid ordinal range,
        # minus whichever are taken, correctly finds a real gap or reports
        # none exists.
        free_ordinal_row = conn.execute(
            "SELECT MIN(o) AS ordinal FROM generate_series(0, ? - 1) AS o "
            "WHERE o NOT IN (SELECT booking_ordinal FROM appointments WHERE hospital_id = ? "
            "AND doctor_id = ? AND scheduled_at = ? AND status = ?)",
            (max_bookings_per_slot, hospital_id, doctor_id, scheduled_at_iso, STATUS_BOOKED),
        ).fetchone()
        if free_ordinal_row["ordinal"] is None:
            raise IntegrityError(f"doctor {doctor_id} has no free booking slot at {scheduled_at_iso}")

        # Item 5 (Spec.md Section 0), extended by the family/multi-person-
        # booking follow-up to also compare NAME, then simplified again by
        # the patient identity SEPARATION follow-up: booking is free (no
        # payment friction), so nothing else stops an accidental/duplicate
        # re-booking with the same doctor.
        #
        # Patient identity SEPARATION: when patient_id is given, this is now
        # a direct, exact check -- does THIS patient_id already have an
        # active appointment with this doctor? -- rather than the older
        # name+age heuristic, which existed only because `patients` used to
        # be one mutable profile per phone with no way to directly identify
        # "this specific family member." More correct by construction now
        # that a real per-profile identity exists.
        effective_name = patient["name"]
        effective_age = patient["age"]
        if patient_id is not None:
            existing_by_patient = conn.execute(
                "SELECT id FROM appointments WHERE hospital_id = ? AND doctor_id = ? "
                "AND patient_id = ? AND status = ? AND id IS DISTINCT FROM ? ORDER BY scheduled_at",
                (hospital_id, doctor_id, patient_id, STATUS_BOOKED, exclude_appointment_id),
            ).fetchall()
            if existing_by_patient:
                raise DuplicateBookingError(
                    "An active appointment with this doctor already exists for this patient.",
                    existing_by_patient[0]["id"],
                )
        elif effective_name is not None and effective_age is not None:
            # Legacy path (no patient_id -- the staff portal): compares this
            # attempt's effective name+age against EACH of this phone's own
            # existing active appointments' OWN denormalized patient_name/
            # patient_age (Item 8 + the family-booking follow-up) -- a real
            # per-booking record, not a single mutable profile field -- so a
            # genuinely different family member (different name, different
            # age, or both) is correctly allowed through, while the same
            # patient re-booking the same doctor is still blocked.
            existing_appointments = conn.execute(
                "SELECT id, patient_name, patient_age FROM appointments WHERE hospital_id = ? AND phone = ? "
                "AND doctor_id = ? AND status = ? AND id IS DISTINCT FROM ? ORDER BY scheduled_at",
                (hospital_id, phone, doctor_id, STATUS_BOOKED, exclude_appointment_id),
            ).fetchall()
            for existing_appt in existing_appointments:
                same_name = (existing_appt["patient_name"] or "").strip().lower() == effective_name.strip().lower()
                same_age = existing_appt["patient_age"] == effective_age
                if same_name and same_age:
                    raise DuplicateBookingError(
                        "An active appointment with this doctor already exists for this patient.", existing_appt["id"],
                    )

        # No retry-on-conflict here (an earlier version of this function had
        # one, left over from before the advisory lock above existed): under
        # the lock, no other transaction can be concurrently computing an
        # ordinal for this doctor+day, so this INSERT cannot lose a race --
        # and critically, retrying-by-issuing-more-statements would NOT be
        # safe here even if it could theoretically happen: Postgres aborts an
        # entire explicit transaction after any failed statement, so a second
        # statement issued after a failed INSERT here would itself fail with
        # "current transaction is aborted", not this table's own
        # IntegrityError -- silently breaking every caller's
        # `except IntegrityError:` handling. Let it propagate straight to the
        # `except BaseException` below instead, which ROLLBACKs correctly and
        # re-raises the SAME, correctly-typed exception.
        # Item 8: `patient` (id/name/age) was already resolved by the
        # _upsert_patient() call before "BEGIN" above -- reused here to
        # denormalize onto the new row, not re-upserted a second time.
        cur = conn.execute(
            "INSERT INTO appointments (hospital_id, phone, department_id, doctor_id, scheduled_at, "
            "booking_ordinal, source, reference_id, patient_id, patient_name, patient_phone, patient_age, "
            "appointment_type_id, consent_given_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (hospital_id, phone, department_id, doctor_id, scheduled_at_iso, free_ordinal_row["ordinal"], source,
             _generate_reference_id(conn, hospital_id), patient["id"], patient["name"], phone, effective_age,
             appointment_type_id, consent_given_at),
        )
        new_id = cur.fetchone()["id"]

        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise

    return get_appointment(hospital_id, new_id)


def get_appointment(hospital_id: int, appointment_id: int) -> Appointment | None:
    conn = get_connection()
    row = conn.execute(
        _APPOINTMENT_SELECT + " AND a.id = ? AND a.hospital_id = ?",
        (appointment_id, hospital_id),
    ).fetchone()
    return _row_to_appointment(row) if row else None


def get_upcoming_appointments_for_phone(hospital_id: int, phone: str, now: datetime | None = None) -> list[Appointment]:
    """A patient's own future, still-booked appointments — soonest first.
    Past appointments and ones already cancelled/rescheduled are excluded here
    (not filtered later) so callers never have to remember to check status."""
    now = now or datetime.now()
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.phone = ? AND a.status = ? AND a.scheduled_at > ? "
        "ORDER BY a.scheduled_at ASC",
        (hospital_id, phone, STATUS_BOOKED, now.isoformat()),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def get_upcoming_appointments(hospital_id: int, offset_hours: float, now: datetime | None = None) -> list[Appointment]:
    """Still-booked appointments scheduled between `now` and `now + offset_hours`
    that haven't had a reminder sent yet *for this specific offset* — a hospital
    can configure multiple offsets (SPEC Section 4's reminder_offsets_hours, e.g.
    24h-before AND 1h-before), each tracked independently via appointment_reminders
    so configuring more than one actually results in more than one reminder per
    appointment, rather than the first one sent silently blocking the rest.
    Used by reminders/scheduler.py, once per offset."""
    now = now or datetime.now()
    cutoff = now + timedelta(hours=offset_hours)
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + """
        AND a.hospital_id = ? AND a.status = ?
          AND a.scheduled_at >= ? AND a.scheduled_at <= ?
          AND NOT EXISTS (
              SELECT 1 FROM appointment_reminders ar
              WHERE ar.appointment_id = a.id AND ar.offset_hours = ?
          )
        ORDER BY a.scheduled_at ASC
        """,
        (hospital_id, STATUS_BOOKED, now.isoformat(), cutoff.isoformat(), offset_hours),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def get_all_appointments_for_hospital(hospital_id: int, limit: int = 500) -> list[Appointment]:
    """Every appointment (any status) for a hospital's own bookings dashboard
    (portal.py, Tier 1 self-serve view) -- most recently scheduled first.
    Unlike get_upcoming_appointments_for_phone()/get_upcoming_appointments(),
    this is intentionally not filtered to booked/future-only: hospital staff
    reviewing their own bookings want to see cancellations/reschedules too."""
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? ORDER BY a.scheduled_at DESC LIMIT ?",
        (hospital_id, limit),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def soft_delete_appointment(hospital_id: int, appointment_id: int) -> bool:
    """Item 3 (Spec.md Section 0): soft-delete only -- stamps deleted_at
    rather than removing the row, preserving this project's standing
    never-hard-delete-appointments convention (cancel_appointment()'s own
    docstring states it explicitly; this extends the same principle to
    "delete"). Restricted to already-resolved appointments (status !=
    'booked') -- an active booking must be cancelled first, not deleted out
    from under the patient without notice. _APPOINTMENT_SELECT's own WHERE
    clause excludes deleted_at IS NOT NULL rows from every normal read, so
    this is enough to hide it everywhere without a matching change at each
    call site."""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE appointments SET deleted_at = ? WHERE id = ? AND hospital_id = ? AND status != ? AND deleted_at IS NULL",
        (datetime.now().isoformat(), appointment_id, hospital_id, STATUS_BOOKED),
    )
    conn.commit()
    return cur.rowcount > 0


def get_total_bookings_count() -> int:
    """Item 7 (Spec.md Section 0): platform-admin lifetime usage stat --
    EVERY row ever inserted into appointments, across every hospital,
    regardless of current status (booked/cancelled/rescheduled/attended/
    no_show) AND regardless of soft-deletion (Item 3) -- a deleted row still
    represents a real historical booking transaction. Deliberately NOT built
    on _APPOINTMENT_SELECT (which excludes soft-deleted rows) -- this is the
    one query in this file that must NOT apply that filter. A reschedule
    counts as a 2nd use (it's a genuinely separate create_appointment() call/
    INSERT), per this feature's own confirmed definition."""
    conn = get_connection()
    return conn.execute("SELECT COUNT(*) AS c FROM appointments").fetchone()["c"]


def get_doctor_appointments_today(hospital_id: int, doctor_id: str, now: datetime | None = None) -> list[Appointment]:
    """Item 4: a specific doctor's own appointments scheduled for today
    (any status, so staff/the doctor can see the full picture -- cancelled/
    rescheduled included -- not just still-booked ones), within the existing
    shared staff portal (no separate doctor-level login exists)."""
    now = now or datetime.now()
    day_start = datetime.combine(now.date(), datetime.min.time()).isoformat()
    day_end = datetime.combine(now.date(), datetime.max.time()).isoformat()
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.doctor_id = ? AND a.scheduled_at >= ? AND a.scheduled_at <= ? "
        "ORDER BY a.scheduled_at ASC",
        (hospital_id, doctor_id, day_start, day_end),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


def mark_reminded(hospital_id: int, appointment_id: int, offset_hours: float) -> None:
    """Records that the reminder for this specific offset has been sent.
    ON CONFLICT DO NOTHING + appointment_reminders' UNIQUE(appointment_id, offset_hours)
    (db/schema.sql) means calling this twice for the same offset is a safe no-op,
    not a duplicate record — that constraint is the actual no-double-send
    guarantee, same pattern as the double-booking index from Phase 8."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO appointment_reminders (hospital_id, appointment_id, offset_hours) VALUES (?, ?, ?) "
        "ON CONFLICT (appointment_id, offset_hours) DO NOTHING",
        (hospital_id, appointment_id, offset_hours),
    )
    conn.commit()


def get_reminded_offsets(hospital_id: int, appointment_id: int) -> list[float]:
    """Which reminder offsets (in hours) have already fired for this appointment."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT offset_hours FROM appointment_reminders WHERE hospital_id = ? AND appointment_id = ? ORDER BY offset_hours DESC",
        (hospital_id, appointment_id),
    ).fetchall()
    return [r["offset_hours"] for r in rows]


def cancel_appointment(hospital_id: int, appointment_id: int) -> None:
    """Marks the appointment cancelled — does not delete the row, so
    cancellation history/audit trail isn't lost. Also stamps updated_at
    (Section 12.8) so the dashboard's activity feed can show this event at
    the time it actually happened, not the original booking's created_at."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ? AND hospital_id = ?",
        (STATUS_CANCELLED, datetime.now().isoformat(), appointment_id, hospital_id),
    )
    conn.commit()


def mark_rescheduled(hospital_id: int, appointment_id: int) -> None:
    """Marks the old appointment as superseded by a reschedule — does not
    delete the row. Callers are responsible for create_appointment()-ing the
    new slot separately (see core/booking_flow.py's reschedule confirm).
    Also stamps updated_at (Section 12.8), same reasoning as cancel_appointment()."""
    conn = get_connection()
    conn.execute(
        "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ? AND hospital_id = ?",
        (STATUS_RESCHEDULED, datetime.now().isoformat(), appointment_id, hospital_id),
    )
    conn.commit()


def mark_attendance(hospital_id: int, appointment_id: int, attended: bool) -> bool:
    """Item 9 (Spec.md Section 0) follow-up: staff-confirmed attended/
    no_show, replacing the dashboard's own no-show HEURISTIC with a real
    recorded outcome for this one appointment.

    Originally only allowed FROM status='booked' and not re-markable --
    relaxed after real portal feedback that staff need full manual control:
    settable any time (not gated on the scheduled time having passed) and
    freely re-toggleable between attended/no_show/back to booked-equivalent
    if staff change their mind, not a one-way door. Allowed FROM 'booked',
    'attended', OR 'no_show' -- deliberately NOT from 'cancelled'/
    'rescheduled' (those appointments didn't happen at all in any sense
    "visited" could mean, so marking attendance on them isn't offered)."""
    conn = get_connection()
    new_status = STATUS_ATTENDED if attended else STATUS_NO_SHOW
    cur = conn.execute(
        "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ? AND hospital_id = ? "
        "AND status IN (?, ?, ?)",
        (new_status, datetime.now().isoformat(), appointment_id, hospital_id,
         STATUS_BOOKED, STATUS_ATTENDED, STATUS_NO_SHOW),
    )
    conn.commit()
    return cur.rowcount > 0


def get_appointments_needing_attendance_review(hospital_id: int, now: datetime | None = None) -> list["Appointment"]:
    """Item 9: still status='booked' but scheduled_at has already passed --
    exactly the set the dashboard's no-show heuristic already identifies,
    surfaced here as real rows for staff to resolve (attended/no_show) via
    mark_attendance(), rather than just a stat-tile count."""
    now = now or datetime.now()
    conn = get_connection()
    rows = conn.execute(
        _APPOINTMENT_SELECT + " AND a.hospital_id = ? AND a.status = ? AND a.scheduled_at < ? ORDER BY a.scheduled_at DESC",
        (hospital_id, STATUS_BOOKED, now.isoformat()),
    ).fetchall()
    return [_row_to_appointment(r) for r in rows]


