"""procedures + procedure_resources subsystem, replaces daycare_duration_options

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-04

Daycare/Procedure rebuild: removes the old duration-picker model
(daycare_duration_options, appointments.duration_hours -- migration 0008)
entirely and replaces it with a real procedure catalog (category + booking
mode INSTANT_BOOKING/APPROVAL_REQUIRED + duration + estimated price range),
hospital-configured pre-procedure instructions, and a multi-resource-
constraint availability engine (bed/chair + equipment + staff pools, each
with its own generated calendar mirroring diagnostic_resources) -- no
equivalent exists anywhere else in this codebase, every other booking type
binds to exactly one resource/timestamp pair.

appointments gains procedure_id + its own nullable procedure_status
sub-status column (REQUESTED/UNDER_REVIEW/APPROVED/REJECTED/CONFIRMED/
COMPLETED/CANCELLED, same separate-sub-status-column convention as
lab_status, migration 0026) + price-at-booking snapshots + an optional
order/prescription reference + a pending "Request Reschedule" slot.
appointment_procedure_resources is a new child table (N rows per one
appointments row) holding which concrete resources were reserved, same "N
rows per one appointment" shape as appointment_lab_tests. Confirmed with the
user: no real daycare bookings exist yet (duration_hours was 0 rows in the
real dev DB), so this migration drops the old model outright rather than
preserving/migrating it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("appointments", "duration_hours")
    op.drop_table("daycare_duration_options")

    op.create_table(
        "procedures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("department_id", sa.Text(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("booking_mode", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("estimated_price_min", sa.Numeric(10, 2), nullable=True),
        sa.Column("estimated_price_max", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "procedures_category_check", "procedures",
        "category IN ('chemotherapy', 'dialysis', 'infusion_therapy', 'dressing_wound_care', "
        "'injection', 'minor_procedure', 'other')",
    )
    op.create_check_constraint(
        "procedures_booking_mode_check", "procedures", "booking_mode IN ('instant', 'approval_required')",
    )
    op.create_check_constraint("procedures_duration_minutes_check", "procedures", "duration_minutes > 0")

    op.create_table(
        "procedure_required_resource_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("procedure_id", sa.Integer(), sa.ForeignKey("procedures.id"), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.UniqueConstraint("procedure_id", "resource_type"),
    )
    op.create_check_constraint(
        "procedure_required_resource_types_type_check", "procedure_required_resource_types",
        "resource_type IN ('bed_chair', 'equipment', 'staff')",
    )

    op.create_table(
        "procedure_instructions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("procedure_id", sa.Integer(), sa.ForeignKey("procedures.id"), nullable=False),
        sa.Column("instruction_type", sa.Text(), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "procedure_instructions_type_check", "procedure_instructions",
        "instruction_type IN ('documents', 'preparation', 'arrival_time', 'medication', "
        "'insurance_authorization', 'other')",
    )

    op.create_table(
        "procedure_resources",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
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
    op.create_check_constraint(
        "procedure_resources_type_check", "procedure_resources", "resource_type IN ('bed_chair', 'equipment', 'staff')",
    )

    op.create_table(
        "procedure_resource_leave",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("resource_id", sa.Text(), sa.ForeignKey("procedure_resources.id"), nullable=False),
        sa.Column("date", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("resource_id", "date"),
    )

    op.create_table(
        "procedure_resource_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("resource_id", sa.Text(), sa.ForeignKey("procedure_resources.id"), nullable=False),
        sa.Column("scheduled_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(now()::text)")),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("resource_id", "scheduled_at"),
    )

    op.create_table(
        "appointment_procedure_resources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("resource_id", sa.Text(), sa.ForeignKey("procedure_resources.id"), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_name", sa.Text(), nullable=False),
    )
    op.create_check_constraint(
        "appointment_procedure_resources_type_check", "appointment_procedure_resources",
        "resource_type IN ('bed_chair', 'equipment', 'staff')",
    )
    op.create_index(
        "idx_appointment_procedure_resources_appointment", "appointment_procedure_resources", ["appointment_id"],
    )
    op.create_index(
        "idx_appointment_procedure_resources_resource", "appointment_procedure_resources", ["resource_id"],
    )

    op.add_column("appointments", sa.Column("procedure_id", sa.Integer(), sa.ForeignKey("procedures.id"), nullable=True))
    op.add_column("appointments", sa.Column("procedure_status", sa.Text(), nullable=True))
    op.create_check_constraint(
        "appointments_procedure_status_check", "appointments",
        "procedure_status IS NULL OR procedure_status IN "
        "('REQUESTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'CONFIRMED', 'COMPLETED', 'CANCELLED')",
    )
    op.add_column("appointments", sa.Column("procedure_estimated_price_min", sa.Numeric(10, 2), nullable=True))
    op.add_column("appointments", sa.Column("procedure_estimated_price_max", sa.Numeric(10, 2), nullable=True))
    op.add_column("appointments", sa.Column("procedure_order_reference", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("procedure_reschedule_requested_at", sa.Text(), nullable=True))

    op.drop_constraint("appointments_doctor_or_resource_chk", "appointments", type_="check")
    op.create_check_constraint(
        "appointments_doctor_or_resource_or_procedure_chk", "appointments",
        "doctor_id IS NOT NULL OR resource_id IS NOT NULL OR procedure_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("appointments_doctor_or_resource_or_procedure_chk", "appointments", type_="check")
    op.create_check_constraint(
        "appointments_doctor_or_resource_chk", "appointments", "doctor_id IS NOT NULL OR resource_id IS NOT NULL",
    )

    op.drop_column("appointments", "procedure_reschedule_requested_at")
    op.drop_column("appointments", "procedure_order_reference")
    op.drop_column("appointments", "procedure_estimated_price_max")
    op.drop_column("appointments", "procedure_estimated_price_min")
    op.drop_constraint("appointments_procedure_status_check", "appointments", type_="check")
    op.drop_column("appointments", "procedure_status")
    op.drop_column("appointments", "procedure_id")

    op.drop_index("idx_appointment_procedure_resources_resource", table_name="appointment_procedure_resources")
    op.drop_index("idx_appointment_procedure_resources_appointment", table_name="appointment_procedure_resources")
    op.drop_table("appointment_procedure_resources")

    op.drop_table("procedure_resource_slots")
    op.drop_table("procedure_resource_leave")
    op.drop_table("procedure_resources")
    op.drop_table("procedure_instructions")
    op.drop_table("procedure_required_resource_types")
    op.drop_table("procedures")

    op.add_column("appointments", sa.Column("duration_hours", sa.Integer(), nullable=True))
    op.create_table(
        "daycare_duration_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint("daycare_duration_options_hours_check", "daycare_duration_options", "hours > 0")
