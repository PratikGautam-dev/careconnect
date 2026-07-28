# slots/scheduler.py
"""
Periodic top-up job (SPEC Section 12.1.1) that keeps every doctor's rolling
window of doctor_slots rows extended as days pass -- same pattern as
reminders/scheduler.py: a plain function core/main.py's /internal/top-up-slots
endpoint calls once per active hospital, meant to be hit by an external cron
job (no in-process scheduler). Idempotent by construction: generate_slots_for_
doctor()'s INSERT OR IGNORE against doctor_slots' UNIQUE(doctor_id,
scheduled_at) means re-running this against an already-topped-up window never
creates duplicate slots, it only adds whatever days have newly entered the
window since the last run.
"""
import db.repository as db


def top_up_slots_for_hospital(hospital_id: int, days_ahead: int = 14) -> int:
    """Extends every doctor's slot window at this hospital. Returns the total
    number of new slot rows inserted across all of the hospital's doctors."""
    total = 0
    for doctor_id in db.list_doctor_ids(hospital_id):
        total += db.generate_slots_for_doctor(hospital_id, doctor_id, days_ahead=days_ahead)
    return total
