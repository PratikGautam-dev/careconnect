"""appointment_types.is_allowed (platform-admin whitelist)

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-30

Adds a platform-admin-controlled whitelist axis to appointment_types,
independent of the existing tenant-controlled is_active toggle
(db/repositories/appointment_types.py's set_appointment_type_active(),
portal/routes/appointment_types.py). is_allowed says whether a tenant may
use a type AT ALL (edit-tenant page, admin/tenants_api.py); is_active is
the tenant's own portal-level on/off switch WITHIN that whitelist -- a row
can never be is_active=True while is_allowed=False, enforced in
set_appointment_type_active() itself.

Defaults to TRUE for every existing row so this migration never narrows
what any already-onboarded tenant can already do -- a platform admin opts
a tenant OUT of a type going forward, this never silently opts anyone out.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointment_types",
        sa.Column("is_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("appointment_types", "is_allowed")
