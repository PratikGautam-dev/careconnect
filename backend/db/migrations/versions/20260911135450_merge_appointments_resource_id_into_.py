"""merge appointments resource_id into diagnostic_test_id

Revision ID: 20260911135450
Revises: 0037
Create Date: 2026-09-11 19:24:50.752966

appointments had two FK columns pointing at diagnostic_tests.id --
resource_id (the one actually wired into the double-booking/advisory-lock
check, the ux_appointments_resource_slot_ordinal_booked unique index, and
the appointments_doctor_or_resource_or_procedure_chk CHECK constraint) and
diagnostic_test_id (a pure duplicate, written to the same value or left
NULL, never read back for any behavior -- confirmed with the user directly,
same "audit every write path first" precedent as migration 0036's own
merge). Left over from before that migration folded diagnostic_resources
into diagnostic_tests, when the two columns genuinely pointed at different
tables. No data is lost: resource_id already carries every value
diagnostic_test_id ever could, so the old diagnostic_test_id column is
dropped outright and resource_id is renamed into its name -- Postgres
carries the FK, the unique index, and the CHECK constraint's column
reference forward automatically on a plain column rename.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260911135450'
down_revision: Union[str, None] = '0037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("appointments", "diagnostic_test_id")
    op.alter_column("appointments", "resource_id", new_column_name="diagnostic_test_id")
    op.execute(
        "ALTER INDEX ux_appointments_resource_slot_ordinal_booked "
        "RENAME TO ux_appointments_diagnostic_test_slot_ordinal_booked"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ux_appointments_diagnostic_test_slot_ordinal_booked "
        "RENAME TO ux_appointments_resource_slot_ordinal_booked"
    )
    op.alter_column("appointments", "diagnostic_test_id", new_column_name="resource_id")
    # No data restored into this column -- it was already a pure duplicate
    # of resource_id (or NULL) before the merge, same "nothing sane to
    # backfill" precedent as migration 0036's own downgrade.
    op.add_column("appointments", sa.Column("diagnostic_test_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=True))
