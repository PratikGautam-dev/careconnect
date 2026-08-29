"""code_sequences: shared, yearly-resetting display-id counter

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29

New shared counter table backing DCCG (CareConnect account)/DCCH (hospital)/
DCCC (clinic)/DCCP (patient, paired with mrn) display ids -- see
db/display_ids.py's own module docstring for the full design. Replaces the
former "derive straight from the row's own SERIAL id, never resets" scheme
for DCCG/DCCH/DCCC, and the dedicated patient_id_counters table for DCCP/mrn
(that table is left in place, just no longer written to going forward --
dropping it is a separate, deliberately-deferred decision).

One row per (prefix, scope_key, period_key) triple:
  - prefix: which entity ("DCCG", "DCCH", "DCCC", or "DCCP").
  - scope_key: "global" for DCCG/DCCH/DCCC, or str(hospital_id) for DCCP
    (patients are still counted per-hospital, same as before).
  - period_key: str(year) for all four -- the whole point of this table is
    that this column lets last_value legitimately restart at 0 every new
    calendar year without colliding with the previous year's row.

No backfill: every already-issued display_id (old, un-dated format) is left
completely untouched. Only a NEW id, generated after this migration ships,
is minted through this table and carries the new "PREFIX-YYYY-NNNNN" shape.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_sequences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prefix", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("prefix", "scope_key", "period_key", name="uq_code_sequences_prefix_scope_period"),
    )


def downgrade() -> None:
    op.drop_table("code_sequences")
