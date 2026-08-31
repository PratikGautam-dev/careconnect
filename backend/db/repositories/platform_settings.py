# db/repositories/platform_settings.py
"""Cross-tenant values only a platform/super admin can change -- as opposed
to every other settings-shaped column in this codebase (hospitals.
business_hours_text, session_timeout_minutes, ...), which a HOSPITAL's own
staff edit for their own tenant only. platform_settings (db/orm_models.py's
PlatformSettings) is a SINGLETON table: exactly one row, id=1, enforced by a
CHECK constraint -- there is no per-hospital override, by design (confirmed
with the user: max_active_patient_links applies identically to every
tenant, it is not a hospital-configurable field)."""
import json
import logging

from sqlalchemy import select, update

from db.connection import get_session
from db.models import DEFAULT_MAX_ACTIVE_PATIENT_LINKS
from db.orm_models import PlatformSettings

logger = logging.getLogger(__name__)

_SINGLETON_ID = 1


def get_platform_settings() -> dict:
    """The one row, always present -- db/init_db.py's own bootstrap
    guarantees it exists (INSERT ... ON CONFLICT DO NOTHING on every
    startup), so this never returns None in practice."""
    session = get_session()
    row = session.execute(select(PlatformSettings).where(PlatformSettings.id == _SINGLETON_ID)).scalar_one()
    try:
        feature_labels = json.loads(row.feature_labels) if row.feature_labels else {}
        if not isinstance(feature_labels, dict):
            feature_labels = {}
    except (TypeError, ValueError):
        feature_labels = {}
    return {
        "max_active_patient_links": row.max_active_patient_links,
        # Migration 0014: ONE value for every hospital -- see this module's
        # own docstring and that migration's for why these moved off
        # hospitals.feature_labels/dpdp_consent_required.
        "feature_labels": feature_labels,
        "dpdp_consent_required": row.dpdp_consent_required,
    }


def get_max_active_patient_links() -> int:
    """The one value flows/*.py's patient-linking cap checks actually read
    at the point of use -- see connectors/tier1.py's own
    get_max_active_patient_links() for why this goes through the Connector
    interface rather than being imported as a raw constant.

    Falls back to DEFAULT_MAX_ACTIVE_PATIENT_LINKS (5) on ANY read failure
    (a transient DB hiccup, or -- in principle unreachable given
    db/init_db.py's own bootstrap -- a genuinely missing singleton row):
    this value gates whether a WhatsApp conversation can add a family
    member, not something worth taking the whole booking/manage-patients
    flow down over. Deliberately NOT caught in get_platform_settings()
    itself -- the platform-admin GET/POST endpoints (admin/
    platform_settings_api.py) should surface a real failure to the admin
    rather than silently reporting a fallback value as if it were the
    true current setting."""
    try:
        return get_platform_settings()["max_active_patient_links"]
    except Exception:
        logger.exception(
            "Failed to read platform_settings.max_active_patient_links -- "
            "falling back to the default (%d)", DEFAULT_MAX_ACTIVE_PATIENT_LINKS,
        )
        return DEFAULT_MAX_ACTIVE_PATIENT_LINKS


def update_platform_settings(
    max_active_patient_links: int, feature_labels: dict[str, str], dpdp_consent_required: bool,
) -> dict:
    """admin/platform_settings_api.py's own write path -- always a full-object
    save (like every other settings form in this codebase), not a partial
    patch. Raises ValueError on an out-of-range max_active_patient_links --
    1 is the practical floor (0 would mean no family member could ever be
    linked, including the patient calling themselves "Self"); 20 is a
    generous ceiling against a fat-fingered entry, not a considered product
    limit. feature_labels/dpdp_consent_required have no such validation here
    -- the route layer already restricts feature_labels keys to REAL_FEATURES
    (mirroring portal/routes/settings.py's old per-hospital validation)."""
    if not (1 <= max_active_patient_links <= 20):
        raise ValueError("max_active_patient_links must be between 1 and 20")
    session = get_session()
    session.execute(
        update(PlatformSettings)
        .where(PlatformSettings.id == _SINGLETON_ID)
        .values(
            max_active_patient_links=max_active_patient_links,
            feature_labels=json.dumps(feature_labels),
            dpdp_consent_required=dpdp_consent_required,
        )
    )
    session.commit()
    return get_platform_settings()
