"""staff_users / role_permissions / super_admins -- RBAC + Redis

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-30

New tables only (docs/rbac-redis-plan.md Phase 1) -- deliberately does NOT
touch doctors.email/password_hash or hospitals.portal_password_hash, and
does not drop anything. Those two removals are explicit follow-up
migrations, run only after Phase 3's routes are cut over and verified (the
plan's own "don't drop in the same deploy that lands the schema" rule) --
this migration lands the destination staff_users can be dual-written/
migrated into while the old doctor-login and shared-portal-password paths
keep working unchanged for anyone not yet moved over.

staff_users unifies Admin/Receptionist/Doctor into one individually-
logged-in-per-person table (email globally unique, no hospital selector at
login) -- doctor_id is set iff role='doctor' (the paired CHECK constraint
below), making a Doctor row here THAT doctor's real login, replacing
doctors.email/password_hash for doctors who've been migrated.
token_version is the actual JWT revocation mechanism (bumped on password
change/deactivation/role change; auth/jwt_session.py's 15-min-TTL access
tokens embed it as a claim and portal/deps.py's get_current_staff()
re-checks it on every request) since a JWT itself has no server-side kill
switch otherwise.

role_permissions is a row per (hospital, role, page) -- not a JSON blob --
since it's read on every permission check and edited cell-by-cell by the
Roles & Permissions admin UI (portal/routes/roles.py); a hospital with zero
rows here falls back to portal/permissions.py's DEFAULT_PERMISSIONS_BY_ROLE
(only relevant for a hospital that predates this feature -- every new
hospital gets its rows seeded explicitly at onboarding).

super_admins is the individual-account replacement for the X-Admin-Secret/
ADMIN_SECRET/TENANTS_ADMIN_SECRET shared-secret gates -- global (not
hospital-scoped, mirrors `users` not `hospital_users`), own token_version/
is_active, verified against its own SUPER_ADMIN_JWT_SECRET so a leaked
staff-JWT secret can never forge a super-admin token or vice versa (same
"a leaked secret should only forge the one thing it's for" precedent
DOCTOR_SECRET vs PORTAL_SECRET already established).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(now()::text)")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("(now()::text)")),
        sa.CheckConstraint("role IN ('admin', 'receptionist', 'doctor')", name="ck_staff_users_role"),
        sa.CheckConstraint(
            "(role = 'doctor') = (doctor_id IS NOT NULL)", name="ck_staff_users_doctor_role_pairing",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ux_staff_users_email", "staff_users", [sa.text("lower(email)")], unique=True, if_not_exists=True,
    )
    op.create_index(
        "ux_staff_users_doctor_id", "staff_users", ["doctor_id"],
        unique=True, postgresql_where=sa.text("doctor_id IS NOT NULL"), if_not_exists=True,
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("page_key", sa.Text(), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_write", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("role IN ('admin', 'receptionist', 'doctor')", name="ck_role_permissions_role"),
        sa.UniqueConstraint("hospital_id", "role", "page_key", name="ux_role_permissions_hospital_role_page"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_role_permissions_hospital_role", "role_permissions", ["hospital_id", "role"], if_not_exists=True,
    )

    op.create_table(
        "super_admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(now()::text)")),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("super_admins")
    op.drop_index("ix_role_permissions_hospital_role", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("ux_staff_users_doctor_id", table_name="staff_users")
    op.drop_index("ux_staff_users_email", table_name="staff_users")
    op.drop_table("staff_users")
