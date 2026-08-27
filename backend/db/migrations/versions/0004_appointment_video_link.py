"""appointments.video_link

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-28

Tele-consultation Phase 2 (docs/per-appointment-type-flow-plan.md) added
this column to schema.sql directly, on a branch that predates Alembic
adoption -- it never made it into the 0001 baseline snapshot (frozen from
a different branch's schema.sql state) or any numbered migration, so any
database that only ever went through `alembic upgrade head` (or the test
fixture's baseline-only path) never got it. A database that DID at some
point run schema.sql's own `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
directly (the old pre-Alembic path) already has it, though -- so this uses
raw IF NOT EXISTS SQL rather than op.add_column(), which errors on an
already-existing column.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS video_link TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS video_link")
