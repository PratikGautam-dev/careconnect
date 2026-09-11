"""add staff detail fields

Revision ID: 20260911174439
Revises: 20260911162026
Create Date: 2026-09-11 23:14:39.810159

The Staff page's mocked columns (department/phone/address/shift/attendance
status/reports-to) becoming real. department_id is only ever set for a
non-doctor (admin/receptionist) row -- a doctor row's department already
comes from doctor_id -> doctors.department_id, so storing it twice would
let the two drift. attendance_status is a manually-set current status (no
check-in/out timestamps, no history table -- confirmed with the user,
that's a separate future attendance module) with a default of 'present' so
every existing row gets one on upgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260911174439'
down_revision: Union[str, None] = '20260911162026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("staff_details", sa.Column("department_id", sa.Text(), sa.ForeignKey("departments.id"), nullable=True))
    op.add_column("staff_details", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("staff_details", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("staff_details", sa.Column("shift", sa.Text(), nullable=True))
    op.add_column("staff_details", sa.Column("reports_to_id", sa.Integer(), sa.ForeignKey("identities.id"), nullable=True))
    op.add_column(
        "staff_details",
        sa.Column("attendance_status", sa.Text(), nullable=False, server_default="present"),
    )
    op.create_check_constraint(
        "ck_staff_details_shift", "staff_details", "shift IS NULL OR shift IN ('day', 'evening', 'night')",
    )
    op.create_check_constraint(
        "ck_staff_details_attendance_status", "staff_details",
        "attendance_status IN ('present', 'on_leave', 'half_day')",
    )
    op.create_check_constraint(
        "ck_staff_details_department_doctor_role", "staff_details", "role != 'doctor' OR department_id IS NULL",
    )
    op.create_check_constraint(
        "ck_staff_details_reports_to_not_self", "staff_details", "reports_to_id IS NULL OR reports_to_id != identity_id",
    )


def downgrade() -> None:
    op.drop_constraint("ck_staff_details_reports_to_not_self", "staff_details", type_="check")
    op.drop_constraint("ck_staff_details_department_doctor_role", "staff_details", type_="check")
    op.drop_constraint("ck_staff_details_attendance_status", "staff_details", type_="check")
    op.drop_constraint("ck_staff_details_shift", "staff_details", type_="check")
    op.drop_column("staff_details", "attendance_status")
    op.drop_column("staff_details", "reports_to_id")
    op.drop_column("staff_details", "shift")
    op.drop_column("staff_details", "address")
    op.drop_column("staff_details", "phone")
    op.drop_column("staff_details", "department_id")
