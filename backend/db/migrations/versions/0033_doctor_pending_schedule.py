"""doctors: pending_* columns for a queued future schedule change

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-09

Preserves an existing behavior that migration 0032's move to live-computed
slots would otherwise have broken: a schedule edit with a future
effective_from must keep serving the OLD pattern for near-term dates and
only switch to the NEW pattern from effective_from onward. With
doctor_slots gone, there's no separate persisted "old pattern's rows" left
to preserve, so the new pattern is queued in these pending_* columns instead
and the CURRENT columns are left untouched until the cutover date -- read at
compute time (db/repositories/doctors.py), not promoted by any job.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("doctors", sa.Column("pending_working_days", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("pending_working_hours", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("pending_slot_duration_minutes", sa.Integer(), nullable=True))
    op.add_column("doctors", sa.Column("pending_breaks", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("pending_daily_booking_limit", sa.Integer(), nullable=True))
    op.add_column("doctors", sa.Column("pending_effective_from", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("doctors", "pending_effective_from")
    op.drop_column("doctors", "pending_daily_booking_limit")
    op.drop_column("doctors", "pending_breaks")
    op.drop_column("doctors", "pending_slot_duration_minutes")
    op.drop_column("doctors", "pending_working_hours")
    op.drop_column("doctors", "pending_working_days")
