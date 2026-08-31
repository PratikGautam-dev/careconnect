"""identities: merge users/staff_users/super_admins into one identity table

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-31

Three principal tables (users: Google-OAuth hospital owners; staff_users:
password-login hospital staff; super_admins: password-login platform
operators) shared an email/name/created_at skeleton but had genuinely
different auth mechanisms (OAuth vs password), scope (M:M-to-hospital vs
1:1 vs global), and revocation (none vs token_version). Confirmed with the
user: consolidate at the DB level using class-table-inheritance rather than
one wide nullable-heavy table -- a shared `identities` table (email,
password_hash, google_id, token_version -- the actual identity/credential
concern) holds NO privilege/role column of its own, plus thin per-context
extension tables (staff_details, super_admin_details) that only hold what's
specific to that context. super_admin_details has no columns beyond its
identity_id PK/FK -- a bare marker table, not a boolean flag on identities
-- deliberately: identities is shared and widely-written (staff creation,
OAuth signup), so a privilege flag there is one stray UPDATE or unrelated
write-path bug away from silently granting platform-wide access, whereas a
separate table means super-admin status requires an actual row, only ever
inserted by the dedicated provisioning path (confirmed with the user, this
safety property outweighs the extra table's minimal overhead).
hospital_users' M:M ownership shape is preserved as `hospital_owners`,
repointed at identities instead of users.

email becomes globally unique across EVERY context here (case-insensitive,
same ux_staff_users_email convention) -- previously users/staff_users/
super_admins were three independently-unique email domains, so in principle
(never observed in this app's actual data) the same email could exist in
more than one. The backfill below merges any such email into ONE identities
row: users' google_id is only ever set via a plain INSERT ... ON CONFLICT DO
NOTHING (never overwrites), while staff_users/super_admins' password_hash/
is_active/token_version use ON CONFLICT DO UPDATE (a password identity always
wins the mutable fields) -- order matters: users backfills first, so any
later staff/super-admin match enriches an existing OAuth identity rather
than the reverse.

NOTHING is dropped or deleted here, per explicit instruction: users,
hospital_users, staff_users, super_admins keep every row exactly as they
are, untouched -- they simply stop being what the application reads/writes
going forward (db/repositories/{users,staff_users,super_admins}.py now
query the new tables; see those files' own updated docstrings). They are
left in place as a historical backup, not wired into any FK from the new
tables, so this migration is purely additive and safe to run against a live
database with existing data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Order matters -- see this module's own docstring: users (OAuth, google_id)
# backfills first via DO NOTHING so it never clobbers a password identity;
# staff_users/super_admins backfill second via DO UPDATE so a password
# identity's mutable fields always win on a genuine email collision.
_BACKFILL_STATEMENTS = [
    """
    INSERT INTO identities (email, name, google_id, created_at)
    SELECT email, name, google_id, created_at FROM users
    ON CONFLICT (lower(email)) DO NOTHING
    """,
    """
    INSERT INTO identities (email, name, password_hash, is_active, token_version, created_at)
    SELECT email, name, password_hash, is_active, token_version, created_at FROM staff_users
    ON CONFLICT (lower(email)) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        is_active = EXCLUDED.is_active,
        token_version = EXCLUDED.token_version
    """,
    """
    INSERT INTO staff_details (identity_id, hospital_id, role, doctor_id)
    SELECT i.id, s.hospital_id, s.role, s.doctor_id
    FROM staff_users s JOIN identities i ON lower(i.email) = lower(s.email)
    ON CONFLICT (identity_id) DO NOTHING
    """,
    """
    INSERT INTO identities (email, name, password_hash, is_active, token_version, created_at)
    SELECT email, name, password_hash, is_active, token_version, created_at FROM super_admins
    ON CONFLICT (lower(email)) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        is_active = EXCLUDED.is_active,
        token_version = EXCLUDED.token_version
    """,
    """
    INSERT INTO super_admin_details (identity_id)
    SELECT i.id FROM super_admins sa JOIN identities i ON lower(i.email) = lower(sa.email)
    ON CONFLICT (identity_id) DO NOTHING
    """,
    """
    INSERT INTO hospital_owners (hospital_id, identity_id, role, created_at)
    SELECT hu.hospital_id, i.id, hu.role, hu.created_at
    FROM hospital_users hu
    JOIN users u ON u.id = hu.user_id
    JOIN identities i ON lower(i.email) = lower(u.email)
    ON CONFLICT (hospital_id, identity_id) DO NOTHING
    """,
]


def upgrade() -> None:
    op.create_table(
        "identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("google_id", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_index("ux_identities_email", "identities", [sa.text("lower(email)")], unique=True)
    op.create_index(
        "ux_identities_google_id", "identities", ["google_id"], unique=True,
        postgresql_where=sa.text("google_id IS NOT NULL"),
    )

    op.create_table(
        "staff_details",
        sa.Column("identity_id", sa.Integer(), sa.ForeignKey("identities.id"), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("doctor_id", sa.Text(), sa.ForeignKey("doctors.id"), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'receptionist', 'doctor')", name="ck_staff_details_role"),
        sa.CheckConstraint("(role = 'doctor') = (doctor_id IS NOT NULL)", name="ck_staff_details_doctor_role_pairing"),
    )
    op.create_index(
        "ux_staff_details_doctor_id", "staff_details", ["doctor_id"], unique=True,
        postgresql_where=sa.text("doctor_id IS NOT NULL"),
    )

    op.create_table(
        "super_admin_details",
        sa.Column("identity_id", sa.Integer(), sa.ForeignKey("identities.id"), primary_key=True),
    )

    op.create_table(
        "hospital_owners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("identity_id", sa.Integer(), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.UniqueConstraint("hospital_id", "identity_id", name="ux_hospital_owners_hospital_identity"),
    )

    conn = op.get_bind()
    for statement in _BACKFILL_STATEMENTS:
        conn.execute(sa.text(statement))


def downgrade() -> None:
    op.drop_table("hospital_owners")
    op.drop_table("super_admin_details")
    op.drop_table("staff_details")
    op.drop_index("ux_identities_google_id", table_name="identities")
    op.drop_index("ux_identities_email", table_name="identities")
    op.drop_table("identities")
