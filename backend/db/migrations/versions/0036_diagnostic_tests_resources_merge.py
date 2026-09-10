"""diagnostic tests/resources merge: a diagnostic_tests row now carries its own schedule

Revision ID: 0036
Revises: 0035
Create Date: 2026-09-10

Diagnostic tests/resources merge (confirmed with the user directly): a
diagnostic_tests row (the catalog entry a patient picks -- name/category/
variants) used to point at a separate diagnostic_resources row that carried
the actual machine/equipment's schedule (working days/hours, slot duration,
breaks, capacity, leave) and an optional department. Hospitals always
created exactly one resource per test 1:1 anyway, so that indirection is
removed: a test now carries its own schedule directly and has no department
at all (a diagnostic/lab booking never has one). appointments.resource_id
re-points from diagnostic_resources.id (text) to diagnostic_tests.id
(integer) -- a test IS the schedulable resource now.

No data is carried forward (confirmed with the user: admins re-enter each
test's schedule fresh in the portal) -- this drops diagnostic_resources and
its leave/slot tables outright rather than attempting a resource-to-test
backfill that would be ambiguous wherever a resource backed more than one
test.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ux_appointments_resource_slot_ordinal_booked", table_name="appointments")
    op.drop_column("appointments", "resource_id")

    op.add_column("diagnostic_tests", sa.Column("working_days", sa.Text(), nullable=False, server_default=""))
    op.add_column("diagnostic_tests", sa.Column("working_hours", sa.Text(), nullable=False, server_default=""))
    op.add_column("diagnostic_tests", sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("diagnostic_tests", sa.Column("breaks", sa.Text(), nullable=False, server_default=""))
    op.add_column("diagnostic_tests", sa.Column("max_bookings_per_slot", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("diagnostic_tests", sa.Column("daily_booking_limit", sa.Integer(), nullable=True))
    op.add_column("diagnostic_tests", sa.Column("effective_from", sa.Text(), nullable=True))
    op.drop_column("diagnostic_tests", "resource_id")

    op.create_table(
        "diagnostic_test_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=False),
        sa.Column("scheduled_at", sa.Text(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("test_id", "scheduled_at"),
    )
    op.create_table(
        "diagnostic_test_leave",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=False),
        sa.Column("date", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("test_id", "date"),
    )

    op.add_column("appointments", sa.Column("resource_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=True))
    op.create_index(
        "ux_appointments_resource_slot_ordinal_booked", "appointments",
        ["resource_id", "scheduled_at", "booking_ordinal"], unique=True,
        postgresql_where=sa.text("status = 'booked' AND resource_id IS NOT NULL"),
    )

    op.drop_table("diagnostic_resource_slots")
    op.drop_table("diagnostic_resource_leave")
    op.drop_table("diagnostic_resources")


def downgrade() -> None:
    op.create_table(
        "diagnostic_resources",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Text(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("working_days", sa.Text(), nullable=False, server_default=""),
        sa.Column("working_hours", sa.Text(), nullable=False, server_default=""),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("breaks", sa.Text(), nullable=False, server_default=""),
        sa.Column("max_bookings_per_slot", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("daily_booking_limit", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "diagnostic_resource_leave",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("resource_id", sa.Text(), sa.ForeignKey("diagnostic_resources.id"), nullable=False),
        sa.Column("date", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("resource_id", "date"),
    )
    op.create_table(
        "diagnostic_resource_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("resource_id", sa.Text(), sa.ForeignKey("diagnostic_resources.id"), nullable=False),
        sa.Column("scheduled_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(now()::text)")),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("resource_id", "scheduled_at"),
    )

    op.drop_index("ux_appointments_resource_slot_ordinal_booked", table_name="appointments")
    op.drop_column("appointments", "resource_id")

    op.drop_table("diagnostic_test_leave")
    op.drop_table("diagnostic_test_slots")

    op.add_column("diagnostic_tests", sa.Column("resource_id", sa.Text(), sa.ForeignKey("diagnostic_resources.id"), nullable=True))
    op.drop_column("diagnostic_tests", "effective_from")
    op.drop_column("diagnostic_tests", "daily_booking_limit")
    op.drop_column("diagnostic_tests", "max_bookings_per_slot")
    op.drop_column("diagnostic_tests", "breaks")
    op.drop_column("diagnostic_tests", "slot_duration_minutes")
    op.drop_column("diagnostic_tests", "working_hours")
    op.drop_column("diagnostic_tests", "working_days")

    op.add_column("appointments", sa.Column("resource_id", sa.Text(), sa.ForeignKey("diagnostic_resources.id"), nullable=True))
    op.create_index(
        "ux_appointments_resource_slot_ordinal_booked", "appointments",
        ["resource_id", "scheduled_at", "booking_ordinal"], unique=True,
        postgresql_where=sa.text("status = 'booked' AND resource_id IS NOT NULL"),
    )
