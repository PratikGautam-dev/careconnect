# slots/scheduler.py
"""
Periodic top-up job (SPEC Section 12.1.1) that keeps diagnostic/procedure
resources' rolling window of *_slots rows extended as days pass -- same
pattern as reminders/scheduler.py: a plain function core/main.py's
/internal/top-up-slots endpoint calls once per active hospital, meant to be
hit by an external cron job (no in-process scheduler). Idempotent by
construction: every generate_slots_for_*()'s INSERT OR IGNORE against its
table's own UNIQUE constraint means re-running this against an
already-topped-up window never creates duplicate slots, it only adds
whatever days have newly entered the window since the last run.

Doctors are NOT covered here anymore (migration 0032): a doctor's grid is
computed live, on demand, with no persisted window that can ever run dry --
see db/repositories/doctors.py's compute_doctor_candidate_slots(). Resources
still use connectors/tier1.py's self-healing top-up (triggered lazily on the
bot's own slot reads) as their real safety net; this endpoint is only an
optional pre-warm for them so the first patient of the day doesn't pay the
generation cost. Found live: nothing was actually hitting this endpoint in
at least one deployment, which is exactly the gap the self-healing path
exists to cover -- kept here for resources since they haven't been converted
to live computation the way doctors have.
"""
import db.repository as db


def top_up_slots_for_hospital(hospital_id: int, days_ahead: int | None = None) -> int:
    """Extends every diagnostic/procedure resource's slot window at this
    hospital, using its own configured future_booking_days unless a caller
    explicitly overrides it. Returns the total number of new slot rows
    inserted."""
    days_ahead = days_ahead if days_ahead is not None else db.get_future_booking_days(hospital_id)
    total = 0
    for resource in db.get_diagnostic_resources(hospital_id):
        total += db.generate_slots_for_resource(hospital_id, resource["id"], days_ahead=days_ahead)
    for resource in db.get_all_procedure_resources_for_hospital(hospital_id):
        if resource["is_active"]:
            total += db.generate_slots_for_procedure_resource(hospital_id, resource["id"], days_ahead=days_ahead)
    return total
