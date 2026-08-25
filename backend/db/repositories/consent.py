# db/repositories/consent.py
"""DPDP Act consent gate (db/schema.sql's own comment on dpdp_consents) --
asked once per (hospital, phone), right after language selection and
before any patient identity is resolved, for a hospital that has turned on
hospitals.dpdp_consent_required."""
from db.connection import get_connection
from db.repositories.accounts import _get_or_create_account_in_conn


def has_agreed_to_dpdp_consent(hospital_id: int, phone: str) -> bool:
    """True only if this (hospital, phone) has an on-file AGREED decision.
    A phone that has never been asked, or that previously tapped "I Do Not
    Agree" (never persisted -- see record_dpdp_consent()'s own docstring),
    both return False here, so both get asked again on their next fresh
    conversation."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM dpdp_consents WHERE hospital_id = ? AND whatsapp_phone = ?",
        (hospital_id, phone),
    ).fetchone()
    return row is not None


def record_dpdp_consent(hospital_id: int, phone: str) -> None:
    """Called ONLY when the patient taps "I Agree" -- declining never calls
    this at all (db/schema.sql's own comment on dpdp_consents explains why
    only agreement is ever persisted). ON CONFLICT DO NOTHING: re-agreeing
    on a later conversation (e.g. a stale/replayed tap after already having
    agreed) must never fail or overwrite the original consented_at."""
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        account = _get_or_create_account_in_conn(conn, phone, phone_number=phone)
        conn.execute(
            "INSERT INTO dpdp_consents (hospital_id, whatsapp_phone, care_connect_account_id) "
            "VALUES (?, ?, ?) ON CONFLICT (hospital_id, whatsapp_phone) DO NOTHING",
            (hospital_id, phone, account["id"]),
        )
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
