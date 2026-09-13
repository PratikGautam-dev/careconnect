"""add patient consent tracking

Revision ID: d2a67f3d2e09
Revises: 5483e272c7c1
Create Date: 2026-09-13 10:21:26.911470

Patient detail page follow-up (confirmed with the user): a Consent
management section listing DPDP / Privacy Policy / Marketing, each a plain
agree-or-disagree state, admin-editable in the portal and audited via the
existing audit_logs table (action "patient.consent_update").

dpdp_consent/privacy_policy_consent are brand-new, patient-scoped, and
start FALSE ("not agreed" reads as "disagreed" -- confirmed with the user,
no separate "not yet asked" state) -- deliberately NOT backfilled from or
linked to the existing phone-scoped dpdp_consents table (that one-time
WhatsApp gate keeps working exactly as it does today; the two aren't
connected yet).

marketing_consent duplicates patient_links.marketing_consent (the existing
WhatsApp-togglable per-link flag, db/repositories/patients.py's
set_marketing_consent()) rather than replacing it: a patient can have zero
active links (a staff-created/walk-in patient with no WhatsApp link at
all), which would otherwise leave admin nothing to toggle. This column is
the durable, always-present fallback + destination for a portal edit;
get_patient_consent() prefers the most-recently-linked ACTIVE link's own
value when one exists (so it still reflects what a linked patient sees on
WhatsApp), falling back to this column otherwise. set_patient_consent()
(a portal edit) and set_marketing_consent() (a WhatsApp toggle) both now
keep this column and any active link's column in sync with each other.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2a67f3d2e09'
down_revision: Union[str, None] = '5483e272c7c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("dpdp_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("patients", sa.Column("privacy_policy_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("patients", sa.Column("marketing_consent", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("patients", "marketing_consent")
    op.drop_column("patients", "privacy_policy_consent")
    op.drop_column("patients", "dpdp_consent")
