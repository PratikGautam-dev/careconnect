"""add attendance_settings page_key

Revision ID: 20260918090200
Revises: 20260918090100
Create Date: 2026-09-18 09:02:00.000000

The new Settings -> Attendance tab (geofence/shift configuration) is
admin-sensitive, unlike the personal attendance/check_in_out pages
(migration 20260914130000) -- same weight as PAGE_STAFF/PAGE_ROLES, so
seeded ONLY for the Admin role, matching how those two pages were seeded
(scoped INSERT, not every role)."""
from typing import Sequence, Union

from alembic import op

revision: str = '20260918090200'
down_revision: Union[str, None] = '20260918090100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO role_permissions (hospital_id, role_id, page_key, can_view, can_write, can_delete)
        SELECT r.hospital_id, r.id, 'attendance_settings', true, true, false
        FROM roles r
        WHERE r.is_protected = TRUE AND r.name = 'Admin'
        ON CONFLICT (hospital_id, role_id, page_key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE page_key = 'attendance_settings'")
