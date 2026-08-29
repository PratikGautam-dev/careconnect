# db/repositories/accounts.py
"""CareConnect account/identity layer (db/schema.sql's own comment on
care_connect_accounts/whatsapp_identities explains the "why global, not
hospital-scoped" reasoning). This is the CONTACT IDENTIFICATION step in the
WhatsApp flow -- resolves "who is messaging us" into a durable account,
independent of and prior to any hospital-scoped patient_links lookup."""
from typing import cast

from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from db.connection import get_session
from db.display_ids import CARE_CONNECT_ACCOUNT_PREFIX, GLOBAL_SCOPE_KEY, generate_yearly_display_id_conn, generate_yearly_display_id_session
from db.orm_models import CareConnectAccount, WhatsappIdentity


def _get_or_create_account_in_session(
    session: Session, provider_user_id: str, phone_number: str | None = None, username: str | None = None,
) -> dict:
    """SQLAlchemy-session counterpart to _get_or_create_account_in_conn()
    below, same resolution logic -- used by callers already migrated off
    get_connection() (db/repositories/consent.py's record_dpdp_consent()).
    The two will collapse into one function once every caller of the
    conn-based version (db/repositories/patients.py's
    _link_patient_under_cap(), still raw SQL) has migrated too -- see
    consent.py's record_dpdp_consent() docstring for why that hasn't
    happened yet. Issues no transaction control of its own, same convention
    as the conn-based version -- callers commit/rollback."""
    identity = session.execute(
        select(WhatsappIdentity).where(WhatsappIdentity.provider_user_id == provider_user_id)
    ).scalar_one_or_none()
    if identity is not None:
        if (phone_number is not None and phone_number != identity.phone_number) or (
            username is not None and username != identity.username
        ):
            session.execute(
                update(WhatsappIdentity)
                .where(WhatsappIdentity.provider_user_id == provider_user_id)
                .values(
                    phone_number=phone_number if phone_number is not None else identity.phone_number,
                    username=username if username is not None else identity.username,
                    updated_at=text("now()::text"),
                )
            )
        return {
            "id": identity.care_connect_account_id,
            "provider_user_id": identity.provider_user_id,
            "username": username if username is not None else identity.username,
            "phone_number": phone_number if phone_number is not None else identity.phone_number,
        }
    # Core insert() with no columns set (not an ORM instance's own
    # save-object path) -- matches "INSERT ... DEFAULT VALUES" exactly, so
    # status/created_at get Postgres's own defaults. See CareConnectAccount's
    # own docstring for why this distinction matters.
    result = cast(CursorResult, session.execute(insert(CareConnectAccount).values()))
    assert result.inserted_primary_key is not None  # INSERT always yields the new primary key
    account_id = result.inserted_primary_key[0]
    # db/display_ids.py -- global, yearly-resetting (see that module's
    # docstring); not yet surfaced in any UI, stored for later use.
    session.execute(
        update(CareConnectAccount)
        .where(CareConnectAccount.id == account_id)
        .values(display_id=generate_yearly_display_id_session(session, CARE_CONNECT_ACCOUNT_PREFIX, GLOBAL_SCOPE_KEY))
    )
    session.execute(
        insert(WhatsappIdentity).values(
            care_connect_account_id=account_id, provider_user_id=provider_user_id,
            username=username, phone_number=phone_number,
        )
    )
    return {
        "id": account_id, "provider_user_id": provider_user_id,
        "username": username, "phone_number": phone_number,
    }


def _get_or_create_account_in_conn(
    conn, provider_user_id: str, phone_number: str | None = None, username: str | None = None,
) -> dict:
    """Same resolution logic as get_or_create_account() below, but issues no
    transaction control of its own -- callers that are already inside a
    BEGIN/COMMIT block (db/repositories/patients.py's _link_patient_under_cap)
    call this directly, on the SAME connection, so the account row it may
    create/update is part of that caller's own transaction rather than a
    separate nested one. get_or_create_account() is the top-level entry point
    for every other caller (webhook/dispatch.py, once per inbound message)."""
    row = conn.execute(
        "SELECT care_connect_account_id, provider_user_id, username, phone_number "
        "FROM whatsapp_identities WHERE provider_user_id = ?",
        (provider_user_id,),
    ).fetchone()
    if row is not None:
        if (phone_number is not None and phone_number != row["phone_number"]) or (
            username is not None and username != row["username"]
        ):
            conn.execute(
                "UPDATE whatsapp_identities SET phone_number = COALESCE(?, phone_number), "
                "username = COALESCE(?, username), updated_at = now()::text WHERE provider_user_id = ?",
                (phone_number, username, provider_user_id),
            )
        return {
            "id": row["care_connect_account_id"], "provider_user_id": row["provider_user_id"],
            "username": username if username is not None else row["username"],
            "phone_number": phone_number if phone_number is not None else row["phone_number"],
        }
    account_row = conn.execute("INSERT INTO care_connect_accounts DEFAULT VALUES RETURNING id").fetchone()
    assert account_row is not None  # INSERT ... RETURNING always returns the inserted row
    account_id = account_row["id"]
    # db/display_ids.py -- global, yearly-resetting (see that module's
    # docstring); not yet surfaced in any UI, stored for later use.
    conn.execute(
        "UPDATE care_connect_accounts SET display_id = ? WHERE id = ?",
        (generate_yearly_display_id_conn(conn, CARE_CONNECT_ACCOUNT_PREFIX, GLOBAL_SCOPE_KEY), account_id),
    )
    conn.execute(
        "INSERT INTO whatsapp_identities (care_connect_account_id, provider_user_id, username, phone_number) "
        "VALUES (?, ?, ?, ?)",
        (account_id, provider_user_id, username, phone_number),
    )
    return {"id": account_id, "provider_user_id": provider_user_id, "username": username, "phone_number": phone_number}


def get_or_create_account(provider_user_id: str, phone_number: str | None = None, username: str | None = None) -> dict:
    """Looks up the whatsapp_identities row for provider_user_id; creates a
    new care_connect_accounts + whatsapp_identities pair if none exists yet.
    On an existing identity, refreshes phone_number/username if the inbound
    values differ from what's on file (a person's WhatsApp display name or
    linked number can change) -- never touches care_connect_accounts.status,
    which is a separate, staff-controlled fact.

    Idempotent and safe to call on every inbound message (webhook/dispatch.py
    does exactly that) -- always resolves to the same account for the same
    provider_user_id. Wraps its work in its own transaction (via
    get_session(), not get_connection() -- this is the ORM path); a caller
    that's already inside its OWN raw-conn transaction
    (db/repositories/patients.py) must use _get_or_create_account_in_conn()
    directly instead, to avoid mixing a psycopg2 connection and a
    SQLAlchemy session in one transaction -- see that function's own
    docstring."""
    session = get_session()
    try:
        result = _get_or_create_account_in_session(
            session, provider_user_id, phone_number=phone_number, username=username,
        )
        session.commit()
    except BaseException:
        session.rollback()
        raise
    return result
