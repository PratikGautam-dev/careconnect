"""replace staff shift enum with a real weekly schedule

Revision ID: 20260913060656
Revises: 20260913052126
Create Date: 2026-09-13 11:36:56.167612

Staff schedule feature (confirmed with the user): staff_details.shift was a
single coarse enum (day/evening/night, each mapped to a hardcoded label) --
no real recurring schedule behind it. Replaced with the exact same
working_days/working_hours/breaks model doctors already have (comma-stored
TEXT, no CHECK constraint -- validated in the application layer only, same
as doctors.working_days/working_hours/breaks). Confirmed no cross-cutting
code depends on shift (isolated to staff_details/the staff routes/hooks),
so this is a clean replace, not an additive column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260913060656'
down_revision: Union[str, None] = '20260913052126'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_staff_details_shift", "staff_details", type_="check")
    op.drop_column("staff_details", "shift")
    op.add_column("staff_details", sa.Column("working_days", sa.Text(), nullable=False, server_default=""))
    op.add_column("staff_details", sa.Column("working_hours", sa.Text(), nullable=False, server_default=""))
    op.add_column("staff_details", sa.Column("breaks", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("staff_details", "breaks")
    op.drop_column("staff_details", "working_hours")
    op.drop_column("staff_details", "working_days")
    op.add_column("staff_details", sa.Column("shift", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_staff_details_shift", "staff_details", "shift IS NULL OR shift IN ('day', 'evening', 'night')",
    )
