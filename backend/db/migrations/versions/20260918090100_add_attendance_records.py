"""add attendance_records table

Revision ID: 20260918090100
Revises: 20260918090000
Create Date: 2026-09-18 09:01:00.000000

The real check-in/check-out module StaffDetail.attendance_status's own
comment (migration 20260911174439) flagged as future work: one row per
(staff, date), written by the new db/repositories/attendance.py's check_in/
check_out/start_break/end_break, read by the /portal/check-in-out (self)
and /portal/attendance (hospital roll-up) pages.

staff_id references identities.id (not staff_details.identity_id directly --
same FK target StaffDetail itself uses) since a staff member's own identity
row is what get_current_staff() resolves. Unique on (staff_id, date) --
check_in()/check_out()/start_break()/end_break() all upsert today's single
row rather than allowing multiple check-ins per day.

break_started_at is the ONE currently-open break's start time (NULL when not
on a break); break_minutes is the running total of every CLOSED break today.
Multiple breaks/day are supported without a child table by just accumulating
into break_minutes each time end_break() closes one.

check_in_verified_method records WHICH of geofence/IP verification actually
passed (or 'none' when the hospital hasn't configured either yet) -- an
audit trail of how this check-in was allowed, not just that it was."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260918090100'
down_revision: Union[str, None] = '20260918090000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_in_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("check_in_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("check_in_ip", sa.Text(), nullable=True),
        sa.Column("check_in_verified_method", sa.Text(), nullable=True),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("check_out_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("check_out_ip", sa.Text(), nullable=True),
        sa.Column("break_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="on_time"),
        sa.Column("late_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("working_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("staff_id", "date", name="ux_attendance_records_staff_date"),
        sa.CheckConstraint(
            "check_in_verified_method IS NULL OR check_in_verified_method IN ('gps', 'ip', 'both', 'none')",
            name="attendance_records_check_in_verified_method_check",
        ),
        sa.CheckConstraint(
            "status IN ('on_time', 'late', 'absent', 'leave', 'half_day')",
            name="attendance_records_status_check",
        ),
    )
    op.create_index("ix_attendance_records_hospital_date", "attendance_records", ["hospital_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_attendance_records_hospital_date", table_name="attendance_records")
    op.drop_table("attendance_records")
