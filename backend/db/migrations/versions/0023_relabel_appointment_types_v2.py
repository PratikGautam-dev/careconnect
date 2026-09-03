"""relabel default appointment types (v2, WhatsApp menu restructuring)

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-02

Follow-up to 0009_relabel_appointment_types.py, same shape: Diagnostic
Booking -> Diagnostic Test, Lab Test Booking -> Lab Test, Daycare Booking ->
Daycare / Procedure -- shorter labels matching the new Tests & Diagnostics
category submenu's row titles. db/repositories/appointment_types.py's
DEFAULT_APPOINTMENT_TYPES is the single source of truth this mirrors for
newly-onboarded hospitals; this migration catches up existing ones.

Only rows still holding the OLD default label are relabeled -- a hospital
that's already relabeled a type via the portal is left alone, same rule
0009 already applies.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RELABELS = (
    ("diagnostic", "Diagnostic Booking", "Diagnostic Test"),
    ("lab", "Lab Test Booking", "Lab Test"),
    ("daycare", "Daycare Booking", "Daycare / Procedure"),
)


def upgrade() -> None:
    conn = op.get_bind()
    for type_id, old_label, new_label in _RELABELS:
        conn.execute(
            sa.text("UPDATE appointment_types SET label = :new_label WHERE id = :type_id AND label = :old_label"),
            {"new_label": new_label, "type_id": type_id, "old_label": old_label},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for type_id, old_label, new_label in _RELABELS:
        conn.execute(
            sa.text("UPDATE appointment_types SET label = :old_label WHERE id = :type_id AND label = :new_label"),
            {"old_label": old_label, "type_id": type_id, "new_label": new_label},
        )
