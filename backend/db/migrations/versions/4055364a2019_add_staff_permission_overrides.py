"""add_staff_permission_overrides

Revision ID: 4055364a2019
Revises: 144a8eabac9a
Create Date: 2026-09-13 19:40:04.284701

User-level permission overrides (see the approved plan at
.claude/plans/federated-enchanting-raven.md): a second, finer-grained layer
on top of the existing per-role `role_permissions` grid -- an admin can now
grant or revoke one specific action on one specific page for one individual
staff member, without touching anyone else on that same role (e.g. give one
particular doctor `delete` on Appointments while the rest of the "Doctor"
role keeps view+write only).

Each of can_view/can_write/can_delete is nullable -- NULL means "no opinion,
inherit whatever the staff member's current role says" -- so a single row
can override just one action while leaving the other two to the role. A row
is only ever written when at least one column is non-NULL (see
db/repositories/staff_permissions.py's upsert, which deletes the row outright
once every column goes back to NULL) -- there's no such thing as a
meaningless all-NULL row sitting in this table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4055364a2019'
down_revision: Union[str, None] = '144a8eabac9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_permission_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_key", sa.Text(), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=True),
        sa.Column("can_write", sa.Boolean(), nullable=True),
        sa.Column("can_delete", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_index(
        "ux_staff_permission_overrides", "staff_permission_overrides",
        ["hospital_id", "staff_id", "page_key"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_staff_permission_overrides", table_name="staff_permission_overrides")
    op.drop_table("staff_permission_overrides")
