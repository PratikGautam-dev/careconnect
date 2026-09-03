"""patient_documents: add document_type category

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-02

WhatsApp menu restructuring: Reports & Prescriptions' new "View
Prescriptions / View Lab Reports / View Diagnostic Reports" submenu rows
need a real filtered query, not the old flat/uncategorized document list --
patient_documents had no category column before this. Nullable-then-
backfill-then-NOT-NULL, same shape as this repo's other add-a-column-then-
tighten migrations: every existing row (uploaded before this category
existed) defaults to "other" rather than guessing a category from the
filename.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patient_documents", sa.Column("document_type", sa.Text(), nullable=True))
    op.execute("UPDATE patient_documents SET document_type = 'other' WHERE document_type IS NULL")
    op.alter_column("patient_documents", "document_type", nullable=False, server_default="other")


def downgrade() -> None:
    op.drop_column("patient_documents", "document_type")
