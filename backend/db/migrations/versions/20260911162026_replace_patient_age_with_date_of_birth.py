"""replace patient age with date of birth

Revision ID: 20260911162026
Revises: 20260911135450
Create Date: 2026-09-11 21:50:26.944578

Patient age (a plain integer collected once during WhatsApp registration)
is replaced with date of birth going forward -- confirmed with the user.
patients.date_of_birth already existed (the staff-portal demographics-edit
path has always written it) but was never connected to age; now it's the
only source of truth, and age is computed on the fly for display wherever
it's still shown, never stored again. patients.age is dropped outright (no
fallback) -- an existing patient with only an age on file just shows a
blank age until a real DOB is entered.

appointments.patient_age (a snapshot used by one legacy duplicate-booking
check that tells apart two family members sharing one phone) becomes
appointments.patient_date_of_birth -- same role, DOB-keyed instead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260911162026'
down_revision: Union[str, None] = '20260911135450'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("patients", "age")
    op.drop_column("appointments", "patient_age")
    op.add_column("appointments", sa.Column("patient_date_of_birth", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "patient_date_of_birth")
    # No data restored -- age was already dropped with no DOB->age
    # conversion possible (a DOB gives an exact age, but not the reverse),
    # same "nothing sane to backfill" precedent as prior migrations in this
    # file's history.
    op.add_column("appointments", sa.Column("patient_age", sa.Integer(), nullable=True))
    op.add_column("patients", sa.Column("age", sa.Integer(), nullable=True))
