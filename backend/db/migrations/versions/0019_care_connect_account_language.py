"""care_connect_accounts.language (global, persisted language preference)

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-30

Language selection follow-up (confirmed with the user): previously
session-only (core/session_store.py), re-asked every time a session times
out. Now persisted once, globally, on the CareConnect account -- same
language at every hospital this person messages, not per-hospital like
dpdp_consents (language is a personal preference, not a hospital-specific
compliance matter). NULL (every existing row) means "never chosen yet" --
flows/router.py's _enter_idle() still shows the picker in that case,
identical to today's behavior.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("care_connect_accounts", sa.Column("language", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("care_connect_accounts", "language")
