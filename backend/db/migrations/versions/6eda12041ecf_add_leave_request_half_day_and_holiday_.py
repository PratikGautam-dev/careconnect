"""add_leave_request_half_day_and_holiday_page

Revision ID: 6eda12041ecf
Revises: 4055364a2019
Create Date: 2026-09-13 23:20:52.260870

Self-service "Holiday Application" page: submits real leave_requests rows
(the already-shipped admin approve/reject workflow), replacing the old
unapproved doctor_leave self-add flow. Not doctor-only -- ANY staff member
(doctor or not) applies for their own leave through it, so its default
permission is view+write for every role, not just Doctor. Two changes:

1. `is_half_day` on leave_requests -- the form's Full day/Half day choice
   (only meaningful for a single-day request; enforced at the route layer,
   not the DB).
2. A backfill of role_permissions for the new "holiday_application" page
   key -- without this, every hospital that onboarded before this page
   existed would resolve it to all-False for every role (get_permission_
   matrix's documented "no rows yet -> all-False" fallback), silently
   hiding the new sidebar item from every staff member already using the
   app, the same class of bug just fixed for the Schedule nav item.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6eda12041ecf'
down_revision: Union[str, None] = '4055364a2019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_requests", sa.Column("is_half_day", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("""
        INSERT INTO role_permissions (hospital_id, role_id, page_key, can_view, can_write, can_delete)
        SELECT r.hospital_id, r.id, 'holiday_application', true, true, false
        FROM roles r
        ON CONFLICT (hospital_id, role_id, page_key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE page_key = 'holiday_application'")
    op.drop_column("leave_requests", "is_half_day")
