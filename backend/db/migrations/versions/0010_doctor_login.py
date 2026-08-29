"""doctors.email / password_hash -- dedicated doctor login

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-29

Additive, nullable columns supporting a new, separate doctor-login auth
path (auth/doctor_session.py, portal/routes/doctor_auth.py,
portal/routes/doctor_portal.py) -- issued/reset by an admin through the
existing shared staff portal (POST /api/portal/doctors/{doctor_id}/login-credentials),
never self-registered. Nullable by design: an existing doctor row with
email IS NULL simply has no login yet, and every doctor-management/booking
path that already reads `doctors` keeps working completely unchanged --
this is additive on top of the shared staff portal, not a replacement for
it.

password_hash uses the exact same PBKDF2-SHA256 scheme as
hospitals.portal_password_hash (db/repositories/hospitals.py's
hash_portal_password()/verify_portal_password()) -- reused as-is for
doctors rather than inventing a second hashing scheme.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("doctors", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("password_hash", sa.Text(), nullable=True))
    op.create_index(
        "ux_doctors_email", "doctors", ["email"],
        unique=True, postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_doctors_email", table_name="doctors")
    op.drop_column("doctors", "password_hash")
    op.drop_column("doctors", "email")
