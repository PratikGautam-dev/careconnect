"""hospital_settings: future_booking_days -- hospital-configurable slot
generation window, replacing the hardcoded 14-day default

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-09

Confirmed with the user: doctor/resource/procedure slot generation was
silently going stale wherever nothing ever hit the external-cron-only
/internal/top-up-slots endpoint (found live: a doctor's window had run out
entirely). This column, plus connectors/tier1.py's new self-healing top-up
check, removes the dependency on that external cron -- the app now tops
itself up automatically, using this hospital-wide window length instead of
the module-level _SLOT_DAYS_AHEAD = 14 constant every generate_slots_for_*
function used to default to.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hospital_settings", sa.Column("future_booking_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "hospital_settings_future_booking_days_check",
        "hospital_settings",
        "future_booking_days IS NULL OR future_booking_days > 0",
    )


def downgrade() -> None:
    op.drop_constraint("hospital_settings_future_booking_days_check", "hospital_settings", type_="check")
    op.drop_column("hospital_settings", "future_booking_days")
