"""merge hospital_owners into staff_details, drop hospital_owners

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-31

hospital_owners (Google-OAuth hospital ownership, M:M) and staff_details
(password-login staff, 1:1 identity_id PK) ended up almost identical --
both are just "this identity, this hospital, this role". Confirmed with the
user: no identity actually owns more than one hospital in practice, so the
M:M shape was never used, and a hospital's role vocabulary stays exactly
admin/receptionist/doctor -- no separate 'owner' role. hospital_owners is
folded into staff_details as an ordinary role='admin' row, then dropped: a
Google-OAuth hospital owner is now simply an admin, same table, same login
path (portal/routes/staff_auth.py's JWT/session, reused directly by
auth/google_oauth.py after this migration) as an admin created through the
staff-management UI. staff_details' existing CHECK constraint (role IN
('admin', 'receptionist', 'doctor')) already permits 'admin', so no
constraint changes are needed here.

ON CONFLICT (identity_id) DO NOTHING on the backfill insert: staff_details'
PK is identity_id alone (1:1, confirmed with the user as the intended
cardinality going forward), so if an identity already has a staff_details
row (e.g. was also created as a password-login admin/receptionist/doctor
independently of their Google-OAuth ownership link), that existing row
wins and the hospital_owners row is simply dropped without a second entry
-- consistent with "one identity, one hospital".

downgrade() recreates hospital_owners' STRUCTURE only; the merged rows stay
in staff_details rather than being un-merged, since there's no way to
distinguish (after the merge) which staff_details rows originated from
hospital_owners vs. were always staff_details -- not a real rollback path,
same caveat 0017's downgrade() already documents for its own tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        """
        INSERT INTO staff_details (identity_id, hospital_id, role, doctor_id)
        SELECT identity_id, hospital_id, 'admin', NULL FROM hospital_owners
        ON CONFLICT (identity_id) DO NOTHING
        """
    ))
    conn.execute(sa.text("DROP TABLE IF EXISTS hospital_owners"))


def downgrade() -> None:
    op.create_table(
        "hospital_owners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("identity_id", sa.Integer(), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.UniqueConstraint("hospital_id", "identity_id", name="ux_hospital_owners_hospital_identity"),
    )
