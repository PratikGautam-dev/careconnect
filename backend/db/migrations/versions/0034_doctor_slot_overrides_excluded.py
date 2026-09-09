"""doctor_slot_overrides: excluded column for outright-removed slots

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-09

"Remove slot" (portal /slots/remove) has always meant deleting a slot
outright -- gone from every view, not just hidden/blocked like the
block/unblock toggle. Under migration 0032's live computation, a
normal-pattern slot has no row to delete: removing it has to persist as its
own exception, distinct from `blocked` (which stays visible in the admin
view so staff can unblock it). `excluded` rows are dropped entirely from
get_doctor_grid()'s output.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "doctor_slot_overrides",
        sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("doctor_slot_overrides", "excluded")
