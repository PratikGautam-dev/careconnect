"""add attendance/check_in_out page_keys

Revision ID: 20260914130000
Revises: 20260914120000
Create Date: 2026-09-14 13:00:00.000000

Two new portal pages, /portal/attendance and /portal/check-in-out
(currently frontend-mock -- real wiring is a later follow-up), now go
through the real Roles & Permissions system (portal/permissions.py's
ALL_PAGES/DEFAULT_PERMISSIONS_BY_ROLE_KIND) instead of being visible to
every signed-in role unconditionally. Confirmed with the user: both default
to view+write for every role EXCEPT the seeded Admin role -- an admin
doesn't check themselves in/out day to day, so unlike holiday_application
(migration 6eda12041ecf, which backfilled every role including Admin) this
backfill is scoped to `roles.is_protected = FALSE`. Admin gets NO row at
all for either page_key; get_permission_matrix()'s own "no row -> all-
False" default does the rest, and an admin can still flip it on for their
own role via Roles & Permissions like any other page -- this is only ever
a starting point, not a hard rule."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260914130000'
down_revision: Union[str, None] = '20260914120000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for page_key in ("attendance", "check_in_out"):
        op.execute(f"""
            INSERT INTO role_permissions (hospital_id, role_id, page_key, can_view, can_write, can_delete)
            SELECT r.hospital_id, r.id, '{page_key}', true, true, false
            FROM roles r
            WHERE r.is_protected = FALSE
            ON CONFLICT (hospital_id, role_id, page_key) DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE page_key IN ('attendance', 'check_in_out')")
