"""add attendance geofence/shift settings

Revision ID: 20260918090000
Revises: 20260914150000
Create Date: 2026-09-18 09:00:00.000000

Real backend for the frontend-mock /portal/check-in-out and /portal/attendance
pages (migration 20260914130000's own docstring flagged real wiring as "a
later follow-up" -- this is that follow-up, plus 20260918090100/090200).

These 9 columns on `hospital_settings` are the admin-configurable geofence +
shift-window policy a hospital sets once via Settings -> Attendance, mirroring
the reference chat's own example config (hospital location + radius, allowed
Wi-Fi/IP, shift start/end, early check-in window, late threshold, optional
auto-checkout). All nullable, same "NULL means not configured yet / use the
code-level default" convention as every other hospital_settings column
(db/repositories/hospital_settings.py) -- a hospital that never opens this
tab keeps today's behavior (no geofence/IP check at all), rather than being
blocked from checking in until an admin fills this in.

attendance_latitude/longitude are a single point per hospital (one tenant =
one physical site, matching how `hospitals` itself is one row per tenant) --
not a per-department/per-building list, out of scope here.

attendance_allowed_ip_cidrs is a comma-separated list of exact IPs and/or
CIDR ranges (e.g. "103.45.67.89,103.45.68.0/24") rather than a normalized
child table -- there are realistically only a handful of a hospital's own
ISP-assigned ranges, the same "plain comma-stored string" convention
reminder_offsets_hours already uses on `hospitals` itself."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260918090000'
down_revision: Union[str, None] = '20260914150000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hospital_settings", sa.Column("attendance_latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_allowed_radius_meters", sa.Integer(), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_allowed_ip_cidrs", sa.Text(), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_shift_start", sa.Text(), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_shift_end", sa.Text(), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_early_checkin_minutes", sa.Integer(), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_late_threshold_minutes", sa.Integer(), nullable=True))
    op.add_column("hospital_settings", sa.Column("attendance_auto_checkout_time", sa.Text(), nullable=True))
    op.create_check_constraint(
        "hospital_settings_attendance_allowed_radius_meters_check",
        "hospital_settings", "attendance_allowed_radius_meters IS NULL OR attendance_allowed_radius_meters > 0",
    )
    op.create_check_constraint(
        "hospital_settings_attendance_early_checkin_minutes_check",
        "hospital_settings", "attendance_early_checkin_minutes IS NULL OR attendance_early_checkin_minutes >= 0",
    )
    op.create_check_constraint(
        "hospital_settings_attendance_late_threshold_minutes_check",
        "hospital_settings", "attendance_late_threshold_minutes IS NULL OR attendance_late_threshold_minutes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("hospital_settings_attendance_late_threshold_minutes_check", "hospital_settings", type_="check")
    op.drop_constraint("hospital_settings_attendance_early_checkin_minutes_check", "hospital_settings", type_="check")
    op.drop_constraint("hospital_settings_attendance_allowed_radius_meters_check", "hospital_settings", type_="check")
    op.drop_column("hospital_settings", "attendance_auto_checkout_time")
    op.drop_column("hospital_settings", "attendance_late_threshold_minutes")
    op.drop_column("hospital_settings", "attendance_early_checkin_minutes")
    op.drop_column("hospital_settings", "attendance_shift_end")
    op.drop_column("hospital_settings", "attendance_shift_start")
    op.drop_column("hospital_settings", "attendance_allowed_ip_cidrs")
    op.drop_column("hospital_settings", "attendance_allowed_radius_meters")
    op.drop_column("hospital_settings", "attendance_longitude")
    op.drop_column("hospital_settings", "attendance_latitude")
