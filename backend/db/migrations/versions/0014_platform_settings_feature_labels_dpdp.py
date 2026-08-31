"""platform_settings: global feature_labels + dpdp_consent_required

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-30

Moves two settings that were previously per-hospital columns
(hospitals.feature_labels, hospitals.dpdp_consent_required -- editable by
each hospital's own staff via /api/portal/settings) onto the platform_settings
singleton instead: confirmed with the user that WhatsApp menu label overrides
and the DPDP Act consent gate should be ONE value applied identically across
every tenant, set only by the platform/super admin, not a per-hospital
self-serve setting.

hospitals.feature_labels/dpdp_consent_required are deliberately NOT dropped
here -- removing a column outright is a separate, later cleanup once nothing
reads them anymore, not something to bundle into the same deploy that stops
reading them (same "additive first, destructive cleanup later" discipline as
0013's own doctors.email/password_hash note). Starts blank/off (not
backfilled from any existing hospital's row -- there's no single correct
"which hospital's value wins" answer) -- the platform admin sets both going
forward via /api/admin/platform-settings.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("platform_settings", sa.Column("feature_labels", sa.Text(), nullable=True))
    op.add_column(
        "platform_settings",
        sa.Column("dpdp_consent_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE platform_settings SET feature_labels = '{}' WHERE feature_labels IS NULL"))


def downgrade() -> None:
    op.drop_column("platform_settings", "dpdp_consent_required")
    op.drop_column("platform_settings", "feature_labels")
