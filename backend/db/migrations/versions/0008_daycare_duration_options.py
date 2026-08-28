"""daycare_duration_options table + appointments.duration_hours

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28

Daycare Phase 2 (docs/per-appointment-type-flow-plan.md): the duration
options shown at the new STATE_AWAITING_DAYCARE_DURATION booking step
(flows/booking/types/daycare.py), hospital-configurable per the user's own
call -- same "seeded fixed catalog, editable via the portal" shape as
appointment_types. appointments.duration_hours is the chosen option's
`hours`, persisted onto the booking itself (same pattern as tele's
video_link column, migration 0004) so it survives the option later being
relabeled or deactivated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daycare_duration_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint("ck_daycare_duration_options_hours_positive", "daycare_duration_options", "hours > 0")
    op.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS duration_hours INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS duration_hours")
    op.drop_table("daycare_duration_options")
