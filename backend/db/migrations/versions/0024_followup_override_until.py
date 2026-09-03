"""appointments: add followup_override_until

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-03

Admin/receptionist follow-up validity override: when a patient contacts the
hospital after their normal follow-up eligibility window
(hospital_settings.followup_validity_days past their attended visit's own
scheduled_at) has already closed, staff can grant extra days without
changing the hospital-wide setting. Set on the specific ATTENDED appointment
the follow-up would be against; get_followup_eligible_appointments() treats
a visit as eligible if it's within the normal window OR today is still
on/before this date. NULL (the default) means no override has ever been
granted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("followup_override_until", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "followup_override_until")
