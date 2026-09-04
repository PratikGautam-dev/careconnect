"""google_calendar_connections: keyed by hospital, not by doctor

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-04

Approved plan revision (confirmed with the user): a single hospital ADMIN
connects ONE Google account for the whole hospital, used to create every
doctor's tele-consultation Meet links -- not each doctor connecting their
own account individually. Doctors never see a "Connect Google Calendar"
button anymore; that control moves to the hospital admin's own Settings
page, gated the same way every other admin-only settings action already is
(require_permission(principal, "settings", "write")), not
portal/routes/doctor_portal.py's per-doctor auth.

Data-preserving, not a destructive rebuild, even though in practice no real
connection has ever been completed (the feature has been blocked the whole
time by Google's own OAuth-app "Testing" mode, which only allows explicitly
pre-approved test-user emails to complete the consent screen -- confirmed
with the user directly). If more than one doctor at the same hospital HAD
somehow connected under the old doctor-keyed shape, this keeps the most
recently updated one for that hospital rather than guessing/erroring, then
repoints the primary key from doctor_id to hospital_id (hospital_id was
already a plain column on every row, just not the key).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep at most one row per hospital_id -- the most recently updated one,
    # in the unlikely event more than one doctor at the same hospital had
    # connected under the old doctor-keyed shape.
    op.execute(
        "DELETE FROM google_calendar_connections "
        "WHERE doctor_id NOT IN ("
        "    SELECT DISTINCT ON (hospital_id) doctor_id FROM google_calendar_connections "
        "    ORDER BY hospital_id, updated_at DESC"
        ")"
    )
    op.drop_constraint("google_calendar_connections_pkey", "google_calendar_connections", type_="primary")
    op.drop_column("google_calendar_connections", "doctor_id")
    op.create_primary_key("google_calendar_connections_pkey", "google_calendar_connections", ["hospital_id"])


def downgrade() -> None:
    op.drop_constraint("google_calendar_connections_pkey", "google_calendar_connections", type_="primary")
    op.add_column("google_calendar_connections", sa.Column("doctor_id", sa.Text(), nullable=True))
    op.create_primary_key("google_calendar_connections_pkey", "google_calendar_connections", ["doctor_id"])
