"""diagnostic tests/variants merge: a diagnostic_tests row now carries its own price

Revision ID: 0037
Revises: 0036
Create Date: 2026-09-10

Diagnostic tests/variants merge (confirmed with the user directly): a
diagnostic_tests row (the catalog entry a patient picks -- name/category/
schedule, since migration 0036) used to point at N diagnostic_test_variants
rows, each carrying its own label/price/preparation_instructions, so a
patient picked a test THEN a variant before booking. In practice a test only
ever needed exactly one priced option, so that indirection is removed: a
test now carries its own price directly, there's no separate variant to
pick, and preparation_instructions (never actually used) is dropped
entirely, both on the test and on the Lab Test basket's own snapshot table
(appointment_lab_tests).

No data is carried forward (confirmed with the user: admins re-enter each
test's price fresh in the portal) -- this drops diagnostic_test_variants
outright rather than attempting a variant-to-test price backfill that would
be ambiguous wherever a test had more than one variant.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("diagnostic_tests", sa.Column("price", sa.Numeric(10, 2), nullable=True))
    op.drop_column("appointment_lab_tests", "diagnostic_test_variant_id")
    op.drop_column("appointment_lab_tests", "variant_label")
    op.drop_column("appointment_lab_tests", "preparation_instructions")
    op.drop_column("appointments", "diagnostic_test_variant_id")
    op.drop_column("appointments", "diagnostic_variant_label")
    op.drop_table("diagnostic_test_variants")


def downgrade() -> None:
    op.create_table(
        "diagnostic_test_variants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("test_id", sa.Integer(), sa.ForeignKey("diagnostic_tests.id"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("preparation_instructions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("appointments", sa.Column("diagnostic_variant_label", sa.Text(), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("diagnostic_test_variant_id", sa.Integer(), sa.ForeignKey("diagnostic_test_variants.id"), nullable=True),
    )
    op.add_column("appointment_lab_tests", sa.Column("preparation_instructions", sa.Text(), nullable=True))
    op.add_column("appointment_lab_tests", sa.Column("variant_label", sa.Text(), nullable=False, server_default="Standard"))
    op.add_column(
        "appointment_lab_tests",
        sa.Column("diagnostic_test_variant_id", sa.Integer(), sa.ForeignKey("diagnostic_test_variants.id"), nullable=True),
    )
    op.drop_column("diagnostic_tests", "price")
