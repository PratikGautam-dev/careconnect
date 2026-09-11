"""add doctor contact and employee fields

Revision ID: 20260911190007
Revises: 20260911174439
Create Date: 2026-09-12 00:30:07.670878

The Doctors page's mocked columns (phone, employee ID, location/room)
becoming real -- same follow-up as migration 20260911174439 did for the
Staff page. phone/employee_id join specialization/qualification as
mandatory fields (confirmed with the user); location stays optional, and
is a plain free-text value (no generated ID scheme) since this schema has
no existing employee-numbering convention to extend.

specialization/qualification were nullable before this -- backfilled to ''
on any existing row before the NOT NULL is added, same reason phone/
employee_id are backfilled right after being added, so this migration
never fails against a hospital that already has doctors on file.

All four get a DB-level server_default of '' (not just backfilled) -- a raw
INSERT that doesn't mention these columns at all (db/seed.py's default-
hospital seeding, e.g.) must keep working unchanged; the Doctors page's own
Add/Edit form and CSV import are what actually block a blank value, via
admin/validation.py's _validate_doctor_fields()."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260911190007'
down_revision: Union[str, None] = '20260911174439'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("doctors", sa.Column("phone", sa.Text(), nullable=True, server_default=""))
    op.add_column("doctors", sa.Column("employee_id", sa.Text(), nullable=True, server_default=""))
    op.add_column("doctors", sa.Column("location", sa.Text(), nullable=True))
    op.execute("UPDATE doctors SET phone = '' WHERE phone IS NULL")
    op.execute("UPDATE doctors SET employee_id = '' WHERE employee_id IS NULL")
    op.execute("UPDATE doctors SET specialization = '' WHERE specialization IS NULL")
    op.execute("UPDATE doctors SET qualification = '' WHERE qualification IS NULL")
    op.alter_column("doctors", "phone", nullable=False)
    op.alter_column("doctors", "employee_id", nullable=False)
    op.alter_column("doctors", "specialization", nullable=False, server_default="")
    op.alter_column("doctors", "qualification", nullable=False, server_default="")


def downgrade() -> None:
    op.alter_column("doctors", "qualification", nullable=True, server_default=None)
    op.alter_column("doctors", "specialization", nullable=True, server_default=None)
    op.alter_column("doctors", "employee_id", nullable=True, server_default=None)
    op.alter_column("doctors", "phone", nullable=True, server_default=None)
    op.drop_column("doctors", "location")
    op.drop_column("doctors", "employee_id")
    op.drop_column("doctors", "phone")
