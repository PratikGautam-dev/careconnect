"""diagnostic_tests/diagnostic_test_variants/diagnostic_resources (+ leave/slots) + appointments columns

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-03

Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5): the
test/variant catalog Diagnostic Test and Lab Test booking picks from, plus a
bookable resource (machine/equipment) independent of any doctor -- schedule
columns mirror `doctors`'/`doctor_slots`' own shape so slot generation reuses
the same algorithm. appointments.doctor_id becomes nullable (a resource-bound
booking has no doctor at all); resource_id/diagnostic_test_id/
diagnostic_test_variant_id/label/price snapshots are added, with a CHECK
ensuring at least one of doctor_id/resource_id is always set, and a
resource-scoped sibling of the existing doctor double-booking unique index.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_table(
        "diagnostic_tests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), sa.ForeignKey("diagnostic_resources.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint("ck_diagnostic_tests_category", "diagnostic_tests", "category IN ('diagnostic', 'lab')")
    op.create_table(
        "diagnostic_test_variants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("preparation_instructions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.alter_column("appointments", "doctor_id", existing_type=sa.Text(), nullable=True)
    op.add_column("appointments", sa.Column("resource_id", sa.Text(), sa.ForeignKey("diagnostic_resources.id"), nullable=True))
    op.add_column("appointments", sa.Column("diagnostic_test_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("diagnostic_test_variant_id", sa.Integer(), sa.ForeignKey("diagnostic_test_variants.id"), nullable=True),
    )
    op.add_column("appointments", sa.Column("diagnostic_test_label", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("diagnostic_variant_label", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("diagnostic_price", sa.Numeric(10, 2), nullable=True))
    op.create_check_constraint(
        "appointments_doctor_or_resource_chk", "appointments", "doctor_id IS NOT NULL OR resource_id IS NOT NULL",
    )
    op.create_index(
        "ux_appointments_resource_slot_ordinal_booked", "appointments",
        ["resource_id", "scheduled_at", "booking_ordinal"], unique=True,
        postgresql_where=sa.text("status = 'booked' AND resource_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_appointments_resource_slot_ordinal_booked", table_name="appointments")
    op.drop_constraint("appointments_doctor_or_resource_chk", "appointments", type_="check")
    op.drop_column("appointments", "diagnostic_price")
    op.drop_column("appointments", "diagnostic_variant_label")
    op.drop_column("appointments", "diagnostic_test_label")
    op.drop_column("appointments", "diagnostic_test_variant_id")
    op.drop_column("appointments", "diagnostic_test_id")
    op.drop_column("appointments", "resource_id")
    op.alter_column("appointments", "doctor_id", existing_type=sa.Text(), nullable=False)
    op.drop_table("diagnostic_test_variants")
    op.drop_constraint("ck_diagnostic_tests_category", "diagnostic_tests", type_="check")
    op.drop_table("diagnostic_tests")
    op.drop_table("diagnostic_resource_slots")
    op.drop_table("diagnostic_resource_leave")
    op.drop_table("diagnostic_resources")
