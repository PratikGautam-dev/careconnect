# db/repositories/accounts.py
"""CareConnect account/identity layer (db/schema.sql's own comment on
care_connect_accounts/whatsapp_identities explains the "why global, not
hospital-scoped" reasoning). This is the CONTACT IDENTIFICATION step in the
WhatsApp flow -- resolves "who is messaging us" into a durable account,
independent of and prior to any hospital-scoped patient_links lookup."""
from db.connection import get_connection


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
    account_id = account_row["id"]
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
    provider_user_id. Wraps its work in its own transaction; a caller that's
    already inside one of its own (db/repositories/patients.py) must use
    _get_or_create_account_in_conn() directly instead, to avoid nesting."""
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        result = _get_or_create_account_in_conn(conn, provider_user_id, phone_number=phone_number, username=username)
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    return result
