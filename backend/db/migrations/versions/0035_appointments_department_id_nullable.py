"""appointments: department_id nullable

Revision ID: 0035
Revises: 0034
Create Date: 2026-09-09

Same precedent migration 0025 already set for doctor_id: a resource-bound
booking (diagnostic/lab/procedure) can have no department at all --
diagnostic_resources.department_id has always been optional
(db/repositories/diagnostic_resources.py's create_resource()) -- but
appointments.department_id stayed NOT NULL, so flows/booking/types/
_diagnostic_shared.py and procedure.py's _resolve_department() silently
fell back to the hospital's FIRST department just to satisfy this
constraint, misrepresenting real bookings as belonging to an arbitrary
department they have nothing to do with. Making this column nullable lets
those bookings honestly record "no department" instead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("appointments", "department_id", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("appointments", "department_id", existing_type=sa.Text(), nullable=False)
