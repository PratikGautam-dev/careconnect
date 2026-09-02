"""hospital_settings: per-hospital self-serve settings, starting with
Follow-up eligibility window + fee lines

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-03

docs/per-appointment-type-flow-plan.md Phase 2 Step 2 follow-up: Follow-up
eligibility now expires -- an ATTENDED appointment stops being eligible for
Follow-up followup_validity_days after its own scheduled_at (NULL = 30-day
code-level default, db/repositories/appointments.py's
DEFAULT_FOLLOWUP_VALIDITY_DAYS).

New table, not more columns on `hospitals` (confirmed with the user -- that
table already carries a long, ad-hoc-grown list of self-serve settings
columns; new ones start here instead, mirroring platform_settings' shape but
per-hospital: one row per hospital_id, 1:1, created lazily on first read/
write rather than at hospital-creation time -- see
db/repositories/hospital_settings.py).

followup_fee / new_consultation_fee: per-hospital fee amounts shown on
Follow-up's confirm/success cards (new_consultation_fee is stored for a later
pass -- New Consultation's own cards don't show it yet). NULL means "no fee
configured," which omits the fee line entirely rather than showing ₹0.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospital_settings",
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), primary_key=True),
        sa.Column("followup_validity_days", sa.Integer(), nullable=True),
        sa.Column("followup_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column("new_consultation_fee", sa.Numeric(10, 2), nullable=True),
        sa.CheckConstraint(
            "followup_validity_days IS NULL OR followup_validity_days > 0",
            name="hospital_settings_followup_validity_days_check",
        ),
        sa.CheckConstraint("followup_fee IS NULL OR followup_fee >= 0", name="hospital_settings_followup_fee_check"),
        sa.CheckConstraint(
            "new_consultation_fee IS NULL OR new_consultation_fee >= 0",
            name="hospital_settings_new_consultation_fee_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("hospital_settings")
