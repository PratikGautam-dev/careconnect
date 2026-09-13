"""dynamic roles

Revision ID: 144a8eabac9a
Revises: 20260913060656
Create Date: 2026-09-13 17:01:11.662793

Dynamic RBAC migration (see the approved plan at
.claude/plans/federated-enchanting-raven.md): introduces a real per-hospital
`roles` table, seeds 3 rows (Admin/Receptionist/Doctor) for every existing
hospital, and backfills `role_id` FK columns on `staff_details`/
`role_permissions` from their old `role` TEXT columns (every hospital's
already-customized `role_permissions` values are preserved untouched -- only
the new FK is populated).

The old `role` TEXT columns are kept (not dropped) -- a custom role's
arbitrary name can never satisfy the old `role IN ('admin','receptionist',
'doctor')` CHECK, so that CHECK is dropped and the column is made nullable
instead, same "kept, untouched, as inert legacy debris" precedent migration
0016/0017 already established for the old staff_users/super_admins tables.
Dropping the column outright would also break dozens of earlier historical
replay statements in db/init_db.py that reference it across the whole
migration timeline (0013 through 20260913060656) -- keeping it, merely
inert, avoids retrofitting idempotency-safety into all of them. Application
code never reads/writes `role` again after this migration; `role_id` is the
only authoritative column going forward.

Roles carry no "is this a doctor role" flag -- doctor-ness is purely
`staff_details.doctor_id IS NOT NULL`, independent of which role a staff
member holds (any role can optionally be linked to a doctor profile). Roles
also carry no general "built-in" flag: only the seeded Admin role is
`is_protected` (undeletable -- reserved for a future super-admin flow, per
product decision), every other role including Receptionist/Doctor/any
custom role is fully rename/delete-able by a portal admin, guarded only by
"no staff currently assigned to it" (see db/repositories/roles.py).

The doctor-pairing CHECK constraints (`ck_staff_details_doctor_role_
pairing`/`ck_staff_details_department_doctor_role`) cannot be preserved as
role-based CHECKs any more since "doctor" is no longer a fixed role name --
both are dropped outright; the only remaining pairing rule (a doctor_id
implies no separate department_id, since the doctor's department comes from
their own profile) is enforced at the application level in
portal/routes/staff.py, independent of role entirely.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '144a8eabac9a'
down_revision: Union[str, None] = '20260913060656'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_index(
        "ux_roles_hospital_name", "roles", [sa.text("hospital_id"), sa.text("lower(name)")], unique=True,
    )

    # Seed 3 real rows per existing hospital -- one INSERT...SELECT per
    # role-kind, not a per-hospital Python loop. Names match the old CHECK's
    # exact 3-value set so the backfill join below is a lossless 1:1 match.
    op.execute("""
        INSERT INTO roles (hospital_id, name, description, is_protected)
        SELECT id, 'Admin', 'Full access to every module by default.', true FROM hospitals
    """)
    op.execute("""
        INSERT INTO roles (hospital_id, name, description, is_protected)
        SELECT id, 'Receptionist', 'Front-desk staff: appointments, patients, messages.', false FROM hospitals
    """)
    op.execute("""
        INSERT INTO roles (hospital_id, name, description, is_protected)
        SELECT id, 'Doctor', 'A doctor with a portal login, linked to their own doctor profile.', false
        FROM hospitals
    """)

    op.add_column("staff_details", sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=True))
    op.add_column("role_permissions", sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True))

    op.execute("""
        UPDATE staff_details sd SET role_id = r.id
        FROM roles r WHERE r.hospital_id = sd.hospital_id AND lower(r.name) = sd.role
    """)
    op.execute("""
        UPDATE role_permissions rp SET role_id = r.id
        FROM roles r WHERE r.hospital_id = rp.hospital_id AND lower(r.name) = rp.role
    """)

    op.alter_column("staff_details", "role_id", nullable=False)
    op.alter_column("role_permissions", "role_id", nullable=False)

    # New unique index for ON CONFLICT (hospital_id, role_id, page_key) --
    # a plain index, not a named constraint, so it stays IF-NOT-EXISTS
    # creatable from db/init_db.py's own idempotent replay. The old
    # UNIQUE(hospital_id, role, page_key) constraint is left in place
    # (harmless -- NULL `role` going forward never collides with itself in
    # a UNIQUE index).
    op.create_index(
        "ux_role_permissions_hospital_role_id_page", "role_permissions", ["hospital_id", "role_id", "page_key"],
        unique=True,
    )
    op.create_index("ix_role_permissions_hospital_role_id", "role_permissions", ["hospital_id", "role_id"])

    # Doctor-pairing invariants move to application-level validation in
    # portal/routes/staff.py -- "doctor" is no longer a fixed role name to
    # CHECK against.
    op.drop_constraint("ck_staff_details_doctor_role_pairing", "staff_details", type_="check")
    op.drop_constraint("ck_staff_details_department_doctor_role", "staff_details", type_="check")
    op.drop_constraint("ck_role_permissions_role", "role_permissions", type_="check")
    op.alter_column("role_permissions", "role", nullable=True)
    op.alter_column("staff_details", "role", nullable=True)


def downgrade() -> None:
    op.execute("UPDATE staff_details sd SET role = lower(r.name) FROM roles r WHERE r.id = sd.role_id AND sd.role IS NULL")
    op.execute("UPDATE role_permissions rp SET role = lower(r.name) FROM roles r WHERE r.id = rp.role_id AND rp.role IS NULL")
    op.alter_column("staff_details", "role", nullable=False)
    op.alter_column("role_permissions", "role", nullable=False)
    op.create_check_constraint(
        "ck_role_permissions_role", "role_permissions", "role IN ('admin', 'receptionist', 'doctor')",
    )
    op.create_check_constraint(
        "ck_staff_details_doctor_role_pairing", "staff_details", "(role = 'doctor') = (doctor_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_staff_details_department_doctor_role", "staff_details", "role != 'doctor' OR department_id IS NULL",
    )

    op.drop_index("ix_role_permissions_hospital_role_id", table_name="role_permissions")
    op.drop_index("ux_role_permissions_hospital_role_id_page", table_name="role_permissions")
    op.drop_column("role_permissions", "role_id")
    op.drop_column("staff_details", "role_id")
    op.drop_index("ux_roles_hospital_name", table_name="roles")
    op.drop_table("roles")
