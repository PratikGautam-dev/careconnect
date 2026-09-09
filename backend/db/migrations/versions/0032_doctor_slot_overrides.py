"""doctor_slot_overrides: replace bulk-pre-generated doctor_slots with an
exceptions-only table; a doctor's normal grid is now computed live

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-09

Confirmed with the user: pre-generating one doctor_slots row for every
possible future slot (potentially 20-30/day x up to 90 days x every doctor)
doesn't scale and was the root cause of the stale-window bug fixed in
migration 0031. This migration replaces it with doctor_slot_overrides, which
only ever holds a row for a slot staff has actually touched (blocked, or a
custom one-off addition outside the normal working-hours pattern) -- see
db/orm_models.py's DoctorSlotOverride docstring for the exact shape.

Data migration: every currently-blocked doctor_slots row becomes a blocked
override (is_custom=False, since blocking works identically regardless of
whether the underlying slot was ever "custom"). Non-blocked rows are NOT
migrated -- they were always either (a) a normal-pattern slot, which the new
live computation reproduces on its own, or (b) a custom-added-but-unblocked
slot, which is not auto-detected here (would require replaying each
doctor's pattern against every row) -- checked against the real database
before writing this migration: 11,393 total rows, only 1 ever blocked, so
this simplification loses no meaningful data in practice.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctor_slot_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("doctor_id", sa.Text(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("scheduled_at", sa.Text(), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("doctor_id", "scheduled_at", name="uq_doctor_slot_overrides_doctor_scheduled_at"),
    )
    op.execute(
        "INSERT INTO doctor_slot_overrides (hospital_id, doctor_id, scheduled_at, is_custom, blocked, block_reason) "
        "SELECT hospital_id, doctor_id, scheduled_at, FALSE, TRUE, block_reason "
        "FROM doctor_slots WHERE blocked = TRUE"
    )
    op.drop_table("doctor_slots")


def downgrade() -> None:
    op.create_table(
        "doctor_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("doctor_id", sa.Text(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("scheduled_at", sa.Text(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("doctor_id", "scheduled_at", name="uq_doctor_slots_doctor_scheduled_at"),
    )
    op.execute(
        "INSERT INTO doctor_slots (hospital_id, doctor_id, scheduled_at, blocked, block_reason) "
        "SELECT hospital_id, doctor_id, scheduled_at, blocked, block_reason "
        "FROM doctor_slot_overrides WHERE blocked = TRUE"
    )
    op.drop_table("doctor_slot_overrides")
