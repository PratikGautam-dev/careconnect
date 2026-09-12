"""add leave requests and leave policy

Revision ID: 20260912065049
Revises: 20260911190251
Create Date: 2026-09-12 12:20:49.034646

Leave Requests admin page (confirmed with the user): any identity with a
staff login (doctor or receptionist role) can have a leave_requests row,
reviewed by an admin into one of pending/approved/rejected. identity_id,
not staff_details -- an identity is the durable "who" (a staff_details row
can in principle be replaced/re-linked), and this mirrors staff_details'
own reports_to_id, which already points at identities for the same reason.

duration is computed from from_date/to_date at read time, never stored --
same "computed, not persisted" precedent as staff's own display id
(ST{id}). decided_by/decided_at are both NULL until an admin acts; both are
always set together (never one without the other) once they are.

hospitals.doctor_annual_leave_days/staff_annual_leave_days are the
portal-admin-configurable policy (confirmed with the user: doctor and
receptionist only, not admin -- admin approves leave, doesn't accrue an
allowance) that a leave balance is computed against: allowance minus the
sum of this identity's approved-request days that fall in the current
calendar year."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260912065049'
down_revision: Union[str, None] = '20260911190251'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEAVE_TYPES = ("casual", "sick", "annual", "maternity", "conference", "personal")
_LEAVE_STATUSES = ("pending", "approved", "rejected")


def upgrade() -> None:
    op.add_column("hospitals", sa.Column("doctor_annual_leave_days", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("hospitals", sa.Column("staff_annual_leave_days", sa.Integer(), nullable=False, server_default="30"))

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("identity_id", sa.Integer(), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("leave_type", sa.Text(), nullable=False),
        sa.Column("from_date", sa.Text(), nullable=False),
        sa.Column("to_date", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("decided_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("now()::text")),
        sa.CheckConstraint(f"leave_type IN {_LEAVE_TYPES}", name="ck_leave_requests_leave_type"),
        sa.CheckConstraint(f"status IN {_LEAVE_STATUSES}", name="ck_leave_requests_status"),
        sa.CheckConstraint("to_date >= from_date", name="ck_leave_requests_date_order"),
    )
    op.create_index("ix_leave_requests_hospital_id", "leave_requests", ["hospital_id"])
    op.create_index("ix_leave_requests_identity_id", "leave_requests", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_leave_requests_identity_id", table_name="leave_requests")
    op.drop_index("ix_leave_requests_hospital_id", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_column("hospitals", "staff_annual_leave_days")
    op.drop_column("hospitals", "doctor_annual_leave_days")
