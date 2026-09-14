"""drop hospitals.privacy_notice_text

Revision ID: 20260914105902
Revises: 6eda12041ecf
Create Date: 2026-09-14 10:59:02.000000

Removes the per-hospital custom "privacy notice text" column (formerly
editable from /portal/settings' Notifications tab, shown to patients on the
WhatsApp bot's Consent & Privacy menu item). Confirmed with the user: this
was a real, live customization, but consent handling will be redesigned
separately later, so the field is being removed outright rather than left
orphaned -- every hospital now shows the same generic default notice
(core/translations/dpdp_consent.py's PRIVACY_NOTICE_DEFAULT), same as a
hospital that had never set a custom one. Every application code path that
read/wrote this column (flows/patient_identity/consent.py, flows/router.py,
webhook/dispatch.py, db/repositories/hospitals.py, portal/routes/settings.py,
admin/tenants_api.py, db/models.py, db/orm_models.py) was already removed in
the change just before this migration."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260914105902'
down_revision: Union[str, None] = '6eda12041ecf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("hospitals", "privacy_notice_text")


def downgrade() -> None:
    op.add_column("hospitals", sa.Column("privacy_notice_text", sa.Text(), nullable=True))
