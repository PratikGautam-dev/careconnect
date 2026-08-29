"""platform_settings: singleton global admin-editable settings

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-29

New table for cross-tenant values only a platform/super admin can change --
as opposed to every other settings-shaped column in this codebase
(hospitals.business_hours_text, session_timeout_minutes, ...), which is a
HOSPITAL's own self-serve setting. Confirmed with the user: max_active_
patient_links applies identically to every tenant, it is NOT a per-hospital
override, so it does not belong on the hospitals table at all.

Singleton by design: exactly one row, id=1, enforced by a CHECK constraint
(not a UNIQUE index on a dummy column) -- there is only ever one platform,
so there is only ever one row. Seeded with the value db/models.py's former
MAX_ACTIVE_PATIENT_LINKS=5 hardcoded constant used (now
DEFAULT_MAX_ACTIVE_PATIENT_LINKS, the seed-only default) so this migration
is a pure refactor of WHERE the value lives, not a behavior change for
anyone upgrading. See db/repositories/platform_settings.py for the read/
update API and admin/platform_settings_api.py for the
TENANTS_ADMIN_SECRET-gated endpoint that edits it going forward.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_MAX_ACTIVE_PATIENT_LINKS = 5


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("max_active_patient_links", sa.Integer(), nullable=False, server_default=str(_DEFAULT_MAX_ACTIVE_PATIENT_LINKS)),
        sa.CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text("INSERT INTO platform_settings (id, max_active_patient_links) VALUES (1, :default_value)"),
        {"default_value": _DEFAULT_MAX_ACTIVE_PATIENT_LINKS},
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
