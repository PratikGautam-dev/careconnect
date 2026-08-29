"""relabel + reorder default appointment types

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-29

Relabels the seeded appointment_types catalog per the user's own explicit
wording pass (Tele-consultation -> Video Consultation, Follow-up ->
Follow-up Consultation, Second Opinion -> Report Review, Diagnostic ->
Diagnostic Booking, Lab Test -> Lab Test Booking, Daycare -> Daycare
Booking), and moves Report Review (second_opinion) to sort after Daycare --
db/repositories/appointment_types.py's DEFAULT_APPOINTMENT_TYPES is the
single source of truth this mirrors, kept in sync by hand.

Only rows still holding the OLD default label are relabeled -- a hospital
that's already relabeled a type via the portal is left alone, same "never
touch again once customized" rule _backfill_appointment_types() already
applies at row-creation time, applied here at label granularity since
that's the only place a hospital can actually customize a row today.
sort_order is unconditional across the board -- there is no portal
capability to reorder appointment types, so no row could hold a
hospital-chosen order worth protecting.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RELABELS = (
    ("followup", "Follow-up", "Follow-up Consultation"),
    ("tele", "Tele-consultation", "Video Consultation"),
    ("diagnostic", "Diagnostic", "Diagnostic Booking"),
    ("lab", "Lab Test", "Lab Test Booking"),
    ("daycare", "Daycare", "Daycare Booking"),
    ("second_opinion", "Second Opinion", "Report Review"),
)

_NEW_SORT_ORDER = ("new", "followup", "tele", "diagnostic", "lab", "daycare", "second_opinion")
_OLD_SORT_ORDER = ("new", "followup", "tele", "second_opinion", "diagnostic", "lab", "daycare")


def upgrade() -> None:
    conn = op.get_bind()
    for type_id, old_label, new_label in _RELABELS:
        conn.execute(
            sa.text("UPDATE appointment_types SET label = :new_label WHERE id = :type_id AND label = :old_label"),
            {"new_label": new_label, "type_id": type_id, "old_label": old_label},
        )
    for sort_order, type_id in enumerate(_NEW_SORT_ORDER):
        conn.execute(
            sa.text("UPDATE appointment_types SET sort_order = :sort_order WHERE id = :type_id"),
            {"sort_order": sort_order, "type_id": type_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for type_id, old_label, new_label in _RELABELS:
        conn.execute(
            sa.text("UPDATE appointment_types SET label = :old_label WHERE id = :type_id AND label = :new_label"),
            {"old_label": old_label, "type_id": type_id, "new_label": new_label},
        )
    for sort_order, type_id in enumerate(_OLD_SORT_ORDER):
        conn.execute(
            sa.text("UPDATE appointment_types SET sort_order = :sort_order WHERE id = :type_id"),
            {"sort_order": sort_order, "type_id": type_id},
        )
