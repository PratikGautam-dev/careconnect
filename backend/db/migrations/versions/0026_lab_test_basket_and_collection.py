"""lab_service_areas + appointment_lab_tests + appointments/hospital_settings columns

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-03

Lab Test Phase 2 follow-up (business spec Sections 4.1-4.4): unlike
Diagnostic Test (one test, one machine, one slot -- already built), a Lab
Test booking is a multi-test BASKET, offers a collection-method choice
(visit the hospital/lab vs. home sample collection), and home collection
needs a serviceable-PIN-code check plus a flat collection charge.

appointment_lab_tests is a new child table (N rows per one appointments row)
holding the basket -- the existing singular diagnostic_test_id/variant/label/
price columns on `appointments` are untouched and keep meaning exactly what
they already mean for a Diagnostic Test booking. lab_service_areas is a new
hospital-configurable list of serviceable PIN codes. appointments gains
collection_method/collection_address/collection_pincode/home_collection_charge
(set only for a Lab Test booking) and lab_status (the post-booking report
lifecycle: booked -> sample_collected -> processing -> report_ready).
hospital_settings gains a flat home_collection_charge fee, same convention as
followup_fee/new_consultation_fee.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hospital_settings", sa.Column("home_collection_charge", sa.Numeric(10, 2), nullable=True))
    op.create_check_constraint(
        "hospital_settings_home_collection_charge_check", "hospital_settings",
        "home_collection_charge IS NULL OR home_collection_charge >= 0",
    )

    op.create_table(
        "lab_service_areas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("pincode", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("hospital_id", "pincode"),
    )

    op.create_table(
        "appointment_lab_tests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("diagnostic_test_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=True),
        sa.Column("diagnostic_test_variant_id", sa.Integer(), sa.ForeignKey("diagnostic_test_variants.id"), nullable=True),
        sa.Column("test_label", sa.Text(), nullable=False),
        sa.Column("variant_label", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("preparation_instructions", sa.Text(), nullable=True),
    )
    op.create_index("idx_appointment_lab_tests_appointment", "appointment_lab_tests", ["appointment_id"])

    op.add_column(
        "appointments",
        sa.Column("collection_method", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "appointments_collection_method_check", "appointments",
        "collection_method IS NULL OR collection_method IN ('visit', 'home')",
    )
    op.add_column("appointments", sa.Column("collection_address", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("collection_pincode", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("home_collection_charge", sa.Numeric(10, 2), nullable=True))
    op.add_column("appointments", sa.Column("lab_status", sa.Text(), nullable=True))
    op.create_check_constraint(
        "appointments_lab_status_check", "appointments",
        "lab_status IS NULL OR lab_status IN ('booked', 'sample_collected', 'processing', 'report_ready')",
    )


def downgrade() -> None:
    op.drop_constraint("appointments_lab_status_check", "appointments", type_="check")
    op.drop_column("appointments", "lab_status")
    op.drop_column("appointments", "home_collection_charge")
    op.drop_column("appointments", "collection_pincode")
    op.drop_column("appointments", "collection_address")
    op.drop_constraint("appointments_collection_method_check", "appointments", type_="check")
    op.drop_column("appointments", "collection_method")

    op.drop_index("idx_appointment_lab_tests_appointment", table_name="appointment_lab_tests")
    op.drop_table("appointment_lab_tests")

    op.drop_table("lab_service_areas")

    op.drop_constraint("hospital_settings_home_collection_charge_check", "hospital_settings", type_="check")
    op.drop_column("hospital_settings", "home_collection_charge")
