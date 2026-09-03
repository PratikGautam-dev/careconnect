"""google_calendar_connections: Google Meet integration for tele-consultation
appointments, alongside (not replacing) the existing Jitsi link

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-03

Renumbered from 0022 to 0025: both this branch and a concurrent one (merged
in the same round -- patient_documents.document_type, the appointment-type
relabel v2, and followup_override_until) independently forked a new
migration from 0021, so 0022-0024 went to the concurrent branch and this one
moved to 0025 to keep the chain linear. Same "migration-numbering collision
between concurrent branches" pattern this project has hit before -- resolved
by renumbering since this migration was never applied to production.

Approved plan (confirmed with the user): a doctor can optionally connect
their own Google account (a SEPARATE OAuth client from GOOGLE_CLIENT_ID/
SECRET's hospital-owner sign-in flow, its own scope -- calendar.events only)
so a tele-consultation booking creates a real Google Calendar event with a
Meet link instead of a Jitsi room. One row per doctor (1:1, doctor_id is both
PK and FK) -- a row's mere existence means "connected"; no lazy blank row.

Deliberately additive and fully backward-compatible: no doctor has a row
here until they explicitly connect (nobody will, until the real
GOOGLE_CALENDAR_CLIENT_ID/SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY env vars are
set in the deployment -- see core/config.py), so
flows/booking/types/tele_consultation.py's fallback-to-Jitsi path is the
only path exercised until then, unchanged.

access_token/refresh_token are stored Fernet-encrypted (core/crypto.py),
never raw -- see db/orm_models.py::GoogleCalendarConnection's own docstring.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_calendar_connections",
        sa.Column("doctor_id", sa.Text(), sa.ForeignKey("doctors.id"), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("google_email", sa.Text(), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", sa.Text(), nullable=False),
        sa.Column("calendar_id", sa.Text(), nullable=False, server_default="primary"),
        sa.Column("connected_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("google_calendar_connections")
