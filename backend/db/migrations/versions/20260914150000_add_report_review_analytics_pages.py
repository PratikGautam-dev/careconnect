"""add report-review/report-analytics page_keys

Revision ID: 20260914150000
Revises: 20260914140000
Create Date: 2026-09-15 00:00:00.000000

"Report review" and "Report analytics" (PortalSidebar.tsx nav items, both
still frontend-only mock pages sharing /portal/report-review -- see that
page's own doc comment) now go through the real Roles & Permissions system
instead of the NO_PERMISSION_GATE_KEYS bypass. New page_keys "report-review"
and "report-analytics" (portal/permissions.py's PAGE_REPORT_REVIEW/
PAGE_REPORT_ANALYTICS), each independently editable per role.

Both are brand new -- no existing "appointments"-style row to clone from --
with DIFFERENT defaults per role kind (see DEFAULT_PERMISSIONS_BY_ROLE_KIND):
Admin gets both (view+write); Receptionist gets Report review (view+write)
and Report analytics view-only; Doctor gets Report review (view+write) but
no Report analytics at all. Scoped by role NAME (admin/receptionist/doctor,
case-insensitive) -- a hospital's custom (non-default) roles get no row,
same fail-closed "all-False until an admin grants it" default any untouched
page_key already has."""
from typing import Sequence, Union

from alembic import op


revision: str = '20260914150000'
down_revision: Union[str, None] = '20260914140000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULTS = {
    "report-review": {"admin": (True, True, False), "receptionist": (True, True, False), "doctor": (True, True, False)},
    "report-analytics": {"admin": (True, True, False), "receptionist": (True, False, False), "doctor": (False, False, False)},
}


def upgrade() -> None:
    for page_key, by_role in _DEFAULTS.items():
        for role_name, (can_view, can_write, can_delete) in by_role.items():
            op.execute(f"""
                INSERT INTO role_permissions (hospital_id, role_id, page_key, can_view, can_write, can_delete)
                SELECT r.hospital_id, r.id, '{page_key}', {can_view}, {can_write}, {can_delete}
                FROM roles r
                WHERE LOWER(r.name) = '{role_name}'
                ON CONFLICT (hospital_id, role_id, page_key) DO NOTHING
            """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE page_key IN ('report-review', 'report-analytics')")
