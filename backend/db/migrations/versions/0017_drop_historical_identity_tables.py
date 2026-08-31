"""drop users/hospital_users/staff_users/super_admins (superseded by 0016)

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-31

Migration 0016 copied every row from these four tables into
identities/staff_details/super_admin_details/hospital_owners and repointed
the application onto the new tables, deliberately leaving the old ones in
place as a safety net. Confirmed with the user, now that the new tables are
verified correct in production: drop the old ones -- nothing reads or
writes them anymore (db/repositories/{users,staff_users,super_admins}.py
docstrings), so keeping them around is just dead weight.

hospital_users is dropped before users (its user_id column FK's into
users.id). staff_users/super_admins have no incoming FKs from anything
still in use.

downgrade() recreates the four tables' STRUCTURE (matching 0001's/0013's
original definitions exactly) but cannot restore their data -- a genuine
DROP TABLE is not reversible. If this needs to be undone, the real recovery
path is a database backup/point-in-time-restore, not this downgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS, not op.drop_table() -- db/init_db.py's own
    # init_db_on_connection() (the path tests and every process's startup
    # actually exercise, see that function's own docstring) already runs the
    # same DROP TABLE IF EXISTS statements on every startup, independent of
    # Alembic. Whichever path reaches a given database first, the other must
    # still be a no-op, same "every CREATE/DROP idempotent" discipline this
    # whole file already follows for its create_table/create_index calls.
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS hospital_users"))
    conn.execute(sa.text("DROP TABLE IF EXISTS users"))
    conn.execute(sa.text("DROP TABLE IF EXISTS staff_users"))
    conn.execute(sa.text("DROP TABLE IF EXISTS super_admins"))


def downgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("google_id", sa.Text(), unique=True, nullable=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
    )
    op.create_table(
        "hospital_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.UniqueConstraint("hospital_id", "user_id", name="hospital_users_hospital_id_user_id_key"),
    )
    op.create_table(
        "staff_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("doctor_id", sa.Text(), sa.ForeignKey("doctors.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
    )
    op.create_index("ux_staff_users_email", "staff_users", [sa.text("lower(email)")], unique=True)
    op.create_index(
        "ux_staff_users_doctor_id", "staff_users", ["doctor_id"], unique=True,
        postgresql_where=sa.text("doctor_id IS NOT NULL"),
    )
    op.create_table(
        "super_admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
    )
