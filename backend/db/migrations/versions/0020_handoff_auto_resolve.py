"""hospitals.handoff_auto_resolve_hours / handoff_requests.resolved_by

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-01

Messages page follow-up: an open handoff with no new activity (from either
side) for a configurable period should auto-resolve instead of sitting open
forever -- hospitals.handoff_auto_resolve_hours (nullable INTEGER, same
"nullable + a code-level default" shape as session_timeout_minutes) is the
per-hospital threshold.

handoff_requests.resolved_by (nullable TEXT) distinguishes an auto-resolve
(stored literally as 'auto') from a real staff member resolving it manually
(stored as that staff member's hashed session token, same value/shape
patient_visit_notes.created_by_session_id already uses) -- so the portal can
tell "staff actually handled this" from "it just timed out unanswered."
NULL for every row that predates this column (resolved before this feature
existed, or never resolved at all).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hospitals", sa.Column("handoff_auto_resolve_hours", sa.Integer(), nullable=True))
    op.add_column("handoff_requests", sa.Column("resolved_by", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("handoff_requests", "resolved_by")
    op.drop_column("hospitals", "handoff_auto_resolve_hours")
