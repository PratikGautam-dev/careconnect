"""add appointment capacity settings

Revision ID: 20260914120000
Revises: 20260914105902
Create Date: 2026-09-14 12:00:00.000000

General settings' "Appointment Settings" card had three fields
(Default Appointment Duration, Buffer Time Between Appointments, Maximum
Appointments Per Day) that were frontend-only mock state with no real
backend behavior. Confirmed with the user: all three should be genuinely
enforced --

- default_appointment_duration_minutes (hospital_settings): the slot
  duration used for a doctor who hasn't set their own (doctors.
  slot_duration_minutes is now nullable -- see below). NULL means "use the
  code-level 30-minute default" (db/repositories/hospital_settings.py's
  DEFAULT_APPOINTMENT_DURATION_MINUTES), same convention as
  future_booking_days.
- buffer_minutes (hospital_settings): a gap enforced between every doctor's
  consecutive candidate slots (db/repositories/doctors.py's
  compute_doctor_candidate_slots()). NULL means "no buffer" (0 minutes).
- max_appointments_per_day (hospital_settings): a hospital-wide cap on
  BOOKED appointments per calendar day, enforced in db/repositories/
  appointments.py's create_appointment() alongside the existing per-doctor
  daily_booking_limit. NULL means "no cap" (unchanged from today).

doctors.slot_duration_minutes is relaxed from NOT NULL DEFAULT 30 to
nullable, with no default -- a doctor can now be saved with this field
left blank (the portal's own Add/Edit Doctor form already allows submitting
it blank; only the server-side validator required it, relaxed in the same
change as this migration), meaning "use this hospital's default duration."
Existing rows keep whatever value they already had (all currently 30, from
the old column default) -- untouched by this migration, no data rewrite."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260914120000'
down_revision: Union[str, None] = '20260914105902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hospital_settings", sa.Column("default_appointment_duration_minutes", sa.Integer(), nullable=True))
    op.add_column("hospital_settings", sa.Column("buffer_minutes", sa.Integer(), nullable=True))
    op.add_column("hospital_settings", sa.Column("max_appointments_per_day", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "hospital_settings_default_appointment_duration_minutes_check",
        "hospital_settings", "default_appointment_duration_minutes IS NULL OR default_appointment_duration_minutes > 0",
    )
    op.create_check_constraint(
        "hospital_settings_buffer_minutes_check",
        "hospital_settings", "buffer_minutes IS NULL OR buffer_minutes >= 0",
    )
    op.create_check_constraint(
        "hospital_settings_max_appointments_per_day_check",
        "hospital_settings", "max_appointments_per_day IS NULL OR max_appointments_per_day > 0",
    )
    op.alter_column("doctors", "slot_duration_minutes", existing_type=sa.Integer(), nullable=True, server_default=None)


def downgrade() -> None:
    op.execute("UPDATE doctors SET slot_duration_minutes = 30 WHERE slot_duration_minutes IS NULL")
    op.alter_column(
        "doctors", "slot_duration_minutes", existing_type=sa.Integer(), nullable=False, server_default="30",
    )
    op.drop_constraint("hospital_settings_max_appointments_per_day_check", "hospital_settings", type_="check")
    op.drop_constraint("hospital_settings_buffer_minutes_check", "hospital_settings", type_="check")
    op.drop_constraint(
        "hospital_settings_default_appointment_duration_minutes_check", "hospital_settings", type_="check",
    )
    op.drop_column("hospital_settings", "max_appointments_per_day")
    op.drop_column("hospital_settings", "buffer_minutes")
    op.drop_column("hospital_settings", "default_appointment_duration_minutes")
