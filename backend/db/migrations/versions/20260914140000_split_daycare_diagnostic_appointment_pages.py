"""split daycare/diagnostic appointments into their own page_keys

Revision ID: 20260914140000
Revises: 20260914130000
Create Date: 2026-09-14 14:00:00.000000

Doctor Appointments, Daycare Appointments, and Lab & Diagnostic
Appointments (three separate sidebar nav items / frontend pages) used to
all share ONE page_key, "appointments", in the Roles & Permissions system
-- confirmed with the user this was wrong: a hospital may want to grant one
category to a role without the other two (e.g. a role that handles Daycare
but never touches Lab & Diagnostic). Introduces PAGE_DAYCARE_APPOINTMENTS
("daycare_appointments") and PAGE_DIAGNOSTIC_APPOINTMENTS
("diagnostic_appointments") in portal/permissions.py, each independently
editable per role via Roles & Permissions.

This backfill CLONES each hospital's EXISTING "appointments"
role_permissions rows onto the two new page_keys (not a fixed default) --
whatever a hospital already granted or denied per role for Doctor
Appointments starts out identical for the other two categories too, so
nothing changes for any existing user on the day this ships. Only a
FUTURE edit via Roles & Permissions can diverge them."""
from typing import Sequence, Union

from alembic import op


revision: str = '20260914140000'
down_revision: Union[str, None] = '20260914130000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for page_key in ("daycare_appointments", "diagnostic_appointments"):
        op.execute(f"""
            INSERT INTO role_permissions (hospital_id, role_id, page_key, can_view, can_write, can_delete)
            SELECT hospital_id, role_id, '{page_key}', can_view, can_write, can_delete
            FROM role_permissions
            WHERE page_key = 'appointments'
            ON CONFLICT (hospital_id, role_id, page_key) DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE page_key IN ('daycare_appointments', 'diagnostic_appointments')")
