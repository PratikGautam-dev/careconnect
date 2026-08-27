# db/repositories/consent.py
"""DPDP Act consent gate (db/schema.sql's own comment on dpdp_consents) --
asked once per (hospital, phone), right after language selection and
before any patient identity is resolved, for a hospital that has turned on
hospitals.dpdp_consent_required."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.orm_models import DpdpConsent
from db.repositories.accounts import _get_or_create_account_in_session


def has_agreed_to_dpdp_consent(hospital_id: int, phone: str) -> bool:
    """True only if this (hospital, phone) has an on-file AGREED decision.
    A phone that has never been asked, or that previously tapped "I Do Not
    Agree" (never persisted -- see record_dpdp_consent()'s own docstring),
    both return False here, so both get asked again on their next fresh
    conversation."""
    session = get_session()
    row = session.execute(
        select(DpdpConsent.id).where(
            DpdpConsent.hospital_id == hospital_id, DpdpConsent.whatsapp_phone == phone,
        )
    ).first()
    return row is not None


def record_dpdp_consent(hospital_id: int, phone: str) -> None:
    """Called ONLY when the patient taps "I Agree" -- declining never calls
    this at all (db/schema.sql's own comment on dpdp_consents explains why
    only agreement is ever persisted). ON CONFLICT DO NOTHING: re-agreeing
    on a later conversation (e.g. a stale/replayed tap after already having
    agreed) must never fail or overwrite the original consented_at.

    Uses _get_or_create_account_in_session() (not the conn-based
    _get_or_create_account_in_conn()) -- db/repositories/patients.py's
    _link_patient_under_cap() still calls the conn-based version directly on
    its own raw connection, so that one stays untouched until patients.py's
    own migration; this function only needed its OWN transaction converted,
    since nothing outside it shares this particular transaction."""
    session = get_session()
    try:
        account = _get_or_create_account_in_session(session, phone, phone_number=phone)
        session.execute(
            pg_insert(DpdpConsent)
            .values(hospital_id=hospital_id, whatsapp_phone=phone, care_connect_account_id=account["id"])
            .on_conflict_do_nothing(index_elements=["hospital_id", "whatsapp_phone"])
        )
        session.commit()
    except BaseException:
        session.rollback()
        raise
