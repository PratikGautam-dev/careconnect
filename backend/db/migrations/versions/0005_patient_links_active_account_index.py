"""patient_links: partial index on (hospital_id, care_connect_account_id)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-28

Supports _link_patient_under_cap()'s (db/repositories/patients.py) active-link
count, now filtered on care_connect_account_id (the durable global identity)
instead of the raw whatsapp_phone string -- mirrors the existing
idx_patient_links_active_phone partial index, same WHERE unlinked_at IS NULL
shape, just keyed on the account instead of the phone.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_patient_links_active_account", "patient_links", ["hospital_id", "care_connect_account_id"],
        unique=False, postgresql_where=sa.text("unlinked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_patient_links_active_account", table_name="patient_links")
