"""care_connect_accounts.display_id, hospitals.display_id

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-28

Two new human-readable display IDs, following the patient_display_id/mrn
precedent (db/models.py) but simpler: both care_connect_accounts and
hospitals are already their own small, global, sequential tables, so their
display id is derived directly from their own already-atomic `id` (Postgres
SERIAL) -- no per-tenant counter table needed, unlike patients. Prefixes and
widths are defined once in db/display_ids.py; this migration's backfill SQL
embeds the same prefix/width values by hand since SQL can't import that
module -- keep the two in sync if a prefix or width ever changes.

Nullable, same as patients.patient_display_id/mrn -- NOT a "sometimes
genuinely unset" state, but every row is created via an INSERT (which can't
know its own `id` yet) followed by an UPDATE that stamps display_id once the
id is known (see db/repositories/accounts.py/hospitals.py); a NOT NULL
constraint would reject that INSERT's intermediate state outright. This
migration's own backfill (below) guarantees no pre-existing row is left
NULL, and every insertion path added alongside this migration sets it before
its own transaction commits, so in practice every row a caller ever reads
already has one -- same "nullable at the schema level, always set in
practice" convention patient_display_id/mrn already established. Uniqueness
is enforced via a partial index (ignoring NULL), same as mrn's own
ux_patients_hospital_mrn.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("care_connect_accounts", sa.Column("display_id", sa.Text(), nullable=True))
    op.add_column("hospitals", sa.Column("display_id", sa.Text(), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE care_connect_accounts SET display_id = 'DCC-ACC-' || lpad(id::text, 6, '0') WHERE display_id IS NULL"))
    conn.execute(sa.text("UPDATE hospitals SET display_id = 'DCC-HOS-' || lpad(id::text, 4, '0') WHERE display_id IS NULL"))

    op.create_index(
        "ux_care_connect_accounts_display_id", "care_connect_accounts", ["display_id"],
        unique=True, postgresql_where=sa.text("display_id IS NOT NULL"),
    )
    op.create_index(
        "ux_hospitals_display_id", "hospitals", ["display_id"],
        unique=True, postgresql_where=sa.text("display_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_hospitals_display_id", table_name="hospitals")
    op.drop_index("ux_care_connect_accounts_display_id", table_name="care_connect_accounts")
    op.drop_column("hospitals", "display_id")
    op.drop_column("care_connect_accounts", "display_id")
