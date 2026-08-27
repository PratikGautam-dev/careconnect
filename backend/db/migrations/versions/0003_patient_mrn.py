"""patients.mrn -- separate clinical/legal record number

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-27

Splits the single patient_display_id column into two: patient_display_id
stays the portal-facing internal id (reformatted to DCC-PAT-<seq> going
forward -- see db/models.py's _generate_patient_identifiers()), and this
new mrn column is the hospital-specific clinical/legal record number
(MRN-<hospital short code>-<seq>). Both share the same per-hospital
sequence number, generated together.

Nullable, same pattern as patient_display_id's own original rollout --
db/init_db.py backfills every existing row (deriving the number from
patient_display_id's own suffix for rows that already have one, so no
counter is wasted / the pairing stays consistent).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("mrn", sa.Text(), nullable=True))
    op.create_index(
        "ux_patients_hospital_mrn", "patients", ["hospital_id", "mrn"],
        unique=True, postgresql_where=sa.text("mrn IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_patients_hospital_mrn", table_name="patients")
    op.drop_column("patients", "mrn")
