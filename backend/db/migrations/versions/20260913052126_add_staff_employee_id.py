"""add staff employee_id

Revision ID: 20260913052126
Revises: d2a67f3d2e09
Create Date: 2026-09-13 10:51:26.464955

Employee ID auto-numbering feature (confirmed with the user): staff_details
gets its own employee_id column, mirroring doctors.employee_id (migration
20260911190007) -- generated server-side (db/repositories/staff_users.py's
create_staff_user(), via db/display_ids.py's generate_employee_id_session())
as EMP-ST-NNNNN for every admin/receptionist row; a doctor-role staff_details
row stays "" (its login already carries an EMP-DC id via the linked doctors
row instead). db/init_db.py's own ALTER TABLE ... ADD COLUMN IF NOT EXISTS
mirror is what a database initialized via init_db_on_connection (not this
migration chain) picks the column up from -- same 3-place convention
(migration + schema.sql + init_db.py) every other additive column here uses.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260913052126'
down_revision: Union[str, None] = 'd2a67f3d2e09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("staff_details", sa.Column("employee_id", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("staff_details", "employee_id")
