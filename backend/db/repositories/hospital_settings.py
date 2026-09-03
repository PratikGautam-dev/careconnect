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

# Follow-up eligibility window (docs/per-appointment-type-flow-plan.md Phase 2
# Step 2 follow-up): the code-level default when a hospital's own
# followup_validity_days is NULL (never configured).
DEFAULT_FOLLOWUP_VALIDITY_DAYS = 30


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
    }


def get_followup_validity_days(hospital_id: int) -> int:
    """The one value flows/booking/types/followup.py actually reads at the
    point of use -- falls back to DEFAULT_FOLLOWUP_VALIDITY_DAYS on a NULL
    (never configured) setting, same "nullable column, code-level default"
    convention hospitals.session_timeout_minutes already uses."""
    return get_hospital_settings(hospital_id)["followup_validity_days"] or DEFAULT_FOLLOWUP_VALIDITY_DAYS


def update_hospital_settings(
    hospital_id: int, followup_validity_days: int | None, followup_fee: float | None,
    new_consultation_fee: float | None, home_collection_charge: float | None = None,
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
            home_collection_charge=home_collection_charge,
        )
        .on_conflict_do_update(
            index_elements=["hospital_id"],
            set_={
                "followup_validity_days": followup_validity_days, "followup_fee": followup_fee,
                "new_consultation_fee": new_consultation_fee, "home_collection_charge": home_collection_charge,
            },
        )
    )
    session.commit()
    return get_hospital_settings(hospital_id)
