"""audit_logs table

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-28

Two-level audit trail (tenant-capability-gating-plan.md's follow-up):
'platform_admin' entries record TENANTS_ADMIN_SECRET-gated changes to a
tenant (tenant_type, admin_capabilities, enabled_features, ...); 'portal'
entries record changes an authenticated tenant's own staff-portal session
makes (doctor/department CRUD, appointment-type toggles, settings updates).

actor_label is free text, not a FK, because neither level has a real
per-individual identity today: platform-admin access is one shared secret
(no per-admin login), and portal access resolves to a Hospital, not an
individual staff member (hospital_users.role is unused, same known
limitation the capability-gating plan already flagged as out of scope). A
free-text column means adding real per-user identity later is a
value-population change, not a schema migration.

hospital_id is nullable because a platform_admin action can in principle
target no single tenant (none exist yet, but the column shouldn't need a
migration the day one does); every 'portal' row and every tenant-scoped
'platform_admin' row sets it. No FK ON DELETE behavior needed -- hospitals
are never hard-deleted in this codebase.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_level", sa.Text(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=True),
        sa.Column("actor_label", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.Text(), nullable=True),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        # ISO-8601 TEXT, not a native TIMESTAMP -- same convention every other
        # timestamp column in this schema follows (db/schema.sql's header
        # comment; db/orm_models.py mirrors it as Mapped[str], never DateTime).
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(now()::text)")),
    )
    op.create_check_constraint(
        "ck_audit_logs_actor_level", "audit_logs", "actor_level IN ('platform_admin', 'portal')"
    )
    op.create_index("ix_audit_logs_hospital_created", "audit_logs", ["hospital_id", "created_at"])
    op.create_index("ix_audit_logs_level_created", "audit_logs", ["actor_level", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_level_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_hospital_created", table_name="audit_logs")
    op.drop_table("audit_logs")
