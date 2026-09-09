"""lab_service_areas: support PIN-code ranges alongside individual PIN codes

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-09

A hospital can now add either a single pincode (unchanged) or a range
(range_start/range_end, both 6-digit numeric strings) as one serviceable
area row. A row is exactly one or the other -- enforced by a CHECK
constraint -- so is_pincode_serviceable() only needs to OR together an
exact match and a numeric BETWEEN.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("lab_service_areas", "pincode", existing_type=sa.Text(), nullable=True)
    op.add_column("lab_service_areas", sa.Column("range_start", sa.Text(), nullable=True))
    op.add_column("lab_service_areas", sa.Column("range_end", sa.Text(), nullable=True))
    op.create_check_constraint(
        "lab_service_areas_single_xor_range_chk",
        "lab_service_areas",
        "(pincode IS NOT NULL AND range_start IS NULL AND range_end IS NULL) OR "
        "(pincode IS NULL AND range_start IS NOT NULL AND range_end IS NOT NULL AND range_start <= range_end)",
    )


def downgrade() -> None:
    op.drop_constraint("lab_service_areas_single_xor_range_chk", "lab_service_areas", type_="check")
    op.execute("DELETE FROM lab_service_areas WHERE pincode IS NULL")
    op.drop_column("lab_service_areas", "range_end")
    op.drop_column("lab_service_areas", "range_start")
    op.alter_column("lab_service_areas", "pincode", existing_type=sa.Text(), nullable=False)
