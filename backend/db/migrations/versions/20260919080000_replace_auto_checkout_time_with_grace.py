"""replace attendance_auto_checkout_time with grace minutes

Revision ID: 20260919080000
Revises: 20260918090200
Create Date: 2026-09-19 08:00:00.000000

attendance_auto_checkout_time (a single hospital-wide "HH:MM" cutoff,
migration 20260918090000) turned out to be the wrong shape: it can't
correctly serve two staff members on different shifts at the same hospital
(e.g. an 11:00-18:00 shift and a 15:00-23:30 shift) -- one fixed clock time
either cuts the later shift off early or leaves the earlier shift's
forgotten check-out open for hours after it should have closed.

Replaced with attendance_auto_checkout_grace_minutes: a hospital-wide
GRACE PERIOD (minutes after shift end), applied on top of each STAFF
MEMBER'S OWN shift end (StaffDetail.working_hours, falling back to the
hospital-wide attendance_shift_end when a staff member has none configured)
-- computed per record in db/repositories/attendance.py's
auto_checkout_overdue(), not stored as a second per-staff column. Nothing
real ever depended on the old column (auto-checkout was never actually
wired up to anything before this), so this is a straight replace, not a
migrate-existing-data change."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260919080000'
down_revision: Union[str, None] = '20260918090200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("hospital_settings", "attendance_auto_checkout_time")
    op.add_column("hospital_settings", sa.Column("attendance_auto_checkout_grace_minutes", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "hospital_settings_attendance_auto_checkout_grace_minutes_check",
        "hospital_settings",
        "attendance_auto_checkout_grace_minutes IS NULL OR attendance_auto_checkout_grace_minutes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "hospital_settings_attendance_auto_checkout_grace_minutes_check", "hospital_settings", type_="check",
    )
    op.drop_column("hospital_settings", "attendance_auto_checkout_grace_minutes")
    op.add_column("hospital_settings", sa.Column("attendance_auto_checkout_time", sa.Text(), nullable=True))
