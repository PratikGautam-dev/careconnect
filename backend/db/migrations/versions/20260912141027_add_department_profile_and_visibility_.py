"""add department profile and visibility fields

Revision ID: 20260912141027
Revises: 20260912065049
Create Date: 2026-09-12 19:40:27.166091

Settings -> Departments tab (mockup-driven rebuild, confirmed with the user
to be real, not mocked): departments were previously just (id, hospital_id,
name), so this adds a profile (floor_wing, consultation_hours, description,
head_doctor_id), an internal is_active status, and three patient-facing
visibility flags.

show_on_frontend/whatsapp_booking_enabled both gate the one real patient
channel this app has (the WhatsApp department picker, see
db.get_departments()) -- online_booking_enabled is stored/toggleable for
forward-compatibility only; there's no separate online booking channel
anywhere in this codebase yet, so it has no enforcement point of its own
today (confirmed with the user, not an oversight).

All four booleans default true (server_default) so an existing department,
or a raw INSERT that doesn't mention these columns (db/seed.py), stays
exactly as visible/bookable as it always was -- this migration can't
silently hide anything that was working before it ran.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260912141027'
down_revision: Union[str, None] = '20260912065049'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("departments", sa.Column("floor_wing", sa.Text(), nullable=True))
    op.add_column("departments", sa.Column("consultation_hours", sa.Text(), nullable=True))
    op.add_column("departments", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "departments",
        sa.Column("head_doctor_id", sa.Text(), sa.ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("departments", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("departments", sa.Column("show_on_frontend", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("departments", sa.Column("online_booking_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("departments", sa.Column("whatsapp_booking_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("departments", "whatsapp_booking_enabled")
    op.drop_column("departments", "online_booking_enabled")
    op.drop_column("departments", "show_on_frontend")
    op.drop_column("departments", "is_active")
    op.drop_column("departments", "head_doctor_id")
    op.drop_column("departments", "description")
    op.drop_column("departments", "consultation_hours")
    op.drop_column("departments", "floor_wing")
