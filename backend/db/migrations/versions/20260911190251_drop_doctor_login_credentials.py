"""drop doctor login credentials

Revision ID: 20260911190251
Revises: 20260911190007
Create Date: 2026-09-12 00:32:51.014265

Removes doctors.email/password_hash (migration 0012's dedicated
doctor-login credential columns, admin-issued via the old
POST /api/portal/doctors/{doctor_id}/login-credentials route) and the
DOCTOR_SECRET-signed /api/doctor/login path that read them
(auth/doctor_session.py, portal/routes/doctor_auth.py -- both deleted
outright, not deprecated in place).

Confirmed with the user this credential path was dead: no frontend UI ever
called that route (grepped -- zero references), so every doctor's login has
always gone through the unified staff login instead (a staff_details row
with role='doctor', linked via doctor_id, authenticating through
POST /api/portal/staff/login) -- see portal/routes/doctor_portal.py's
_require_doctor(), simplified in this same change to only use that path.
Dropping these columns outright, not leaving them nullable/unused, since
nothing reads or writes them any more."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260911190251'
down_revision: Union[str, None] = '20260911190007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ux_doctors_email", table_name="doctors")
    op.drop_column("doctors", "password_hash")
    op.drop_column("doctors", "email")


def downgrade() -> None:
    op.add_column("doctors", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("password_hash", sa.Text(), nullable=True))
    op.create_index(
        "ux_doctors_email", "doctors", ["email"],
        unique=True, postgresql_where=sa.text("email IS NOT NULL"),
    )
