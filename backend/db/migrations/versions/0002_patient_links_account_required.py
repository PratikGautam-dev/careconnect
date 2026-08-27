"""patient_links.care_connect_account_id NOT NULL

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-27

care_connect_account_id was nullable because one write path
(db/init_db.py's _backfill_patient_links()) inserted patient_links rows
without it, relying on a separate _backfill_care_connect_accounts() pass
to fill them in afterward. That backfill function is gone now --
_backfill_patient_links() resolves/creates the CareConnectAccount inline
at INSERT time, same as db/repositories/patients.py's
_link_patient_under_cap() already did -- so every patient_links row is
stamped with a real account before this migration ever runs. No data
backfill needed here, just the constraint.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("patient_links", "care_connect_account_id", nullable=False)


def downgrade() -> None:
    op.alter_column("patient_links", "care_connect_account_id", nullable=True)
