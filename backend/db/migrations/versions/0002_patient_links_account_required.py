"""patient_links.care_connect_account_id NOT NULL

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-27

care_connect_account_id was nullable because one write path
(db/init_db.py's _backfill_patient_links()) inserted patient_links rows
without it, relying on a separate _backfill_care_connect_accounts() pass
to fill them in afterward. _backfill_patient_links() now resolves/creates
the CareConnectAccount inline at INSERT time instead, same as
db/repositories/patients.py's _link_patient_under_cap() already did -- but
that only guarantees NEW rows are stamped. Any row already sitting in a
real database from before this rollout can still be NULL here, so this
migration backfills those first (same resolution logic the old
_backfill_care_connect_accounts() used) before enforcing NOT NULL --
skipping the backfill step here was the bug in the original version of
this migration, caught after it crashed init_db() (and the whole app) on
a database that actually had legacy NULL rows, unlike the dev DB this was
first tested against.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    phones = [
        row[0] for row in conn.execute(sa.text(
            "SELECT DISTINCT whatsapp_phone FROM patient_links WHERE care_connect_account_id IS NULL"
        )).fetchall()
    ]
    for phone in phones:
        account_row = conn.execute(
            sa.text("SELECT care_connect_account_id FROM whatsapp_identities WHERE provider_user_id = :phone"),
            {"phone": phone},
        ).fetchone()
        if account_row is not None:
            account_id = account_row[0]
        else:
            account_id = conn.execute(
                sa.text("INSERT INTO care_connect_accounts DEFAULT VALUES RETURNING id")
            ).scalar()
            conn.execute(
                sa.text(
                    "INSERT INTO whatsapp_identities (care_connect_account_id, provider_user_id, phone_number) "
                    "VALUES (:account_id, :phone, :phone)"
                ),
                {"account_id": account_id, "phone": phone},
            )
        conn.execute(
            sa.text(
                "UPDATE patient_links SET care_connect_account_id = :account_id "
                "WHERE whatsapp_phone = :phone AND care_connect_account_id IS NULL"
            ),
            {"account_id": account_id, "phone": phone},
        )
    op.alter_column("patient_links", "care_connect_account_id", nullable=False)


def downgrade() -> None:
    op.alter_column("patient_links", "care_connect_account_id", nullable=True)
