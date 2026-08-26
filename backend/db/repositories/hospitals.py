# db/repositories/hospitals.py
"""Hospital CRUD, multi-tenant routing lookups, and the staff-portal login
password hash (SPEC Section 12.2). Split out of db/repository.py -- see
ARCHITECTURE_PLAN.md Phase 1."""
import hashlib
import hmac
import json as json_lib
import os

from db.connection import get_connection
from db.models import Hospital
from db.repositories.appointment_types import DEFAULT_APPOINTMENT_TYPES

# --- Hospitals (SPEC Section 12.2: multi-tenant routing, Phase 9) ---

_PBKDF2_ITERATIONS = 100_000


def hash_portal_password(password: str) -> str:
    """Salted PBKDF2-SHA256, stdlib only (no new dependency for what's still a
    'basic protection, not production-grade auth' project) -- used for the
    Section 12.7 hospital-staff bookings portal login, which is stored as an
    irreversible hash (unlike access_token/app_secret, which the app must be
    able to read back to call Meta's API with -- a login password never needs
    to be reversed, only verified, so there's no reason to store it in a
    reversible form the way those are). Stored as 'salt_hex:hash_hex'."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{digest.hex()}"


def verify_portal_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split(":", 1)
    except (ValueError, AttributeError):
        return False
    salt = bytes.fromhex(salt_hex)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _row_to_hospital(row) -> Hospital:
    try:
        offsets = json_lib.loads(row["reminder_offsets_hours"])
        if not isinstance(offsets, list) or not offsets:
            raise ValueError
    except (TypeError, ValueError):
        offsets = [24]
    try:
        enabled_features = json_lib.loads(row["enabled_features"])
        if not isinstance(enabled_features, list):
            raise ValueError
    except (TypeError, ValueError):
        # NULL (not yet backfilled -- db/init_db.py's _backfill_enabled_features()
        # should have already run by the time anything queries this, but fail
        # safe to "nothing enabled" rather than crash a row read) or malformed.
        enabled_features = []
    try:
        feature_labels = json_lib.loads(row["feature_labels"])
        if not isinstance(feature_labels, dict):
            raise ValueError
    except (TypeError, ValueError):
        feature_labels = {}
    # Tenant-type-driven capability gating: None (column genuinely NULL, or
    # malformed) is meaningfully different from `[]` (an explicit, deliberate
    # "no capabilities") -- None means "not set, fall back to
    # DEFAULT_CAPABILITIES_BY_TYPE[tenant_type]" (get_capabilities()'s own
    # job, not this row-mapper's), so it's preserved as None rather than
    # coerced to a list here.
    admin_capabilities_raw = row["admin_capabilities"]
    if admin_capabilities_raw is None:
        admin_capabilities = None
    else:
        try:
            admin_capabilities = json_lib.loads(admin_capabilities_raw)
            if not isinstance(admin_capabilities, list):
                raise ValueError
        except (TypeError, ValueError):
            admin_capabilities = None
    return Hospital(
        id=row["id"],
        name=row["name"],
        whatsapp_phone_number_id=row["whatsapp_phone_number_id"],
        access_token=row["meta_access_token_ref"],
        app_secret=row["app_secret_ref"],
        timezone=row["timezone"],
        welcome_message_text=row["welcome_message_text"],
        reminder_offsets_hours=offsets,
        reminder_template_name=row["reminder_template_name"],
        is_active=bool(row["is_active"]),
        data_tier=row["data_tier"],
        external_api_base_url=row["external_api_base_url"],
        external_api_key=row["external_api_key"],
        portal_password_hash=row["portal_password_hash"],
        enabled_features=enabled_features,
        feature_labels=feature_labels,
        closing_message_text=row["closing_message_text"],
        business_hours_text=row["business_hours_text"],
        default_language=row["default_language"] or "en",
        language_prompt_enabled=(
            True if row["language_prompt_enabled"] is None else bool(row["language_prompt_enabled"])
        ),
        session_timeout_minutes=row["session_timeout_minutes"],
        require_patient_confirmation=bool(row["require_patient_confirmation"]),
        privacy_notice_text=row["privacy_notice_text"],
        tenant_type=row["tenant_type"] or "hospital",
        admin_capabilities=admin_capabilities,
        dpdp_consent_required=bool(row["dpdp_consent_required"]),
    )


def find_hospital_by_phone_number_id(phone_number_id: str) -> Hospital | None:
    """The entry point for per-message multi-tenant routing (SPEC Section 12.2):
    given the phone_number_id from an incoming webhook's `metadata`, resolve which
    hospital received it. Only active hospitals are matched — a deactivated
    hospital's number should be treated the same as an unrecognized one."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM hospitals WHERE whatsapp_phone_number_id = ? AND is_active = 1",
        (phone_number_id,),
    ).fetchone()
    return _row_to_hospital(row) if row else None


def get_active_hospitals() -> list[Hospital]:
    """Used by reminders/scheduler.py's caller (core/main.py) to loop over every
    active hospital rather than a single startup-resolved one."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM hospitals WHERE is_active = 1 ORDER BY id").fetchall()
    return [_row_to_hospital(r) for r in rows]


def get_all_hospitals() -> list[Hospital]:
    """Every hospital regardless of is_active -- admin/onboarding.py's tenant
    list page (Section 12.1 follow-up: closing the "onboarding is self-serve,
    correcting it isn't" gap) needs to show every onboarded tenant, not just
    active ones, so there's somewhere to find a deactivated tenant's id too."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM hospitals ORDER BY id").fetchall()
    return [_row_to_hospital(r) for r in rows]


def get_hospital(hospital_id: int) -> Hospital | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM hospitals WHERE id = ?", (hospital_id,)).fetchone()
    return _row_to_hospital(row) if row else None


def find_hospital_by_portal_password(password: str) -> Hospital | None:
    """portal.py's login: which hospital does this password belong to. Each
    hash carries its own random salt (hash_portal_password()), so two
    hospitals CAN pick the identical password and still get different stored
    hashes -- there's no way to look one up by an equality WHERE clause, only
    by hashing the candidate against every stored hash and checking for a
    match. Fine at this project's scale (dozens/hundreds of hospitals, not
    millions); an actual login-throughput bottleneck would need a different
    scheme, but isn't a real concern yet."""
    for hospital in get_all_hospitals():
        if hospital.portal_password_hash and hospital.is_active:
            if verify_portal_password(password, hospital.portal_password_hash):
                return hospital
    return None


def create_hospital(
    name: str,
    whatsapp_phone_number_id: str,
    access_token: str | None = None,
    app_secret: str | None = None,
    timezone: str = "UTC",
    welcome_message_text: str | None = None,
    reminder_offsets_hours: list[float] | None = None,
    reminder_template_name: str | None = None,
    data_tier: str = "tier1",
    external_api_base_url: str | None = None,
    external_api_key: str | None = None,
    portal_password: str | None = None,
    enabled_features: list[str] | None = None,
    feature_labels: dict[str, str] | None = None,
    closing_message_text: str | None = None,
    business_hours_text: str | None = None,
    default_language: str | None = None,
    language_prompt_enabled: bool = True,
    session_timeout_minutes: int | None = None,
    require_patient_confirmation: bool = False,
    privacy_notice_text: str | None = None,
    tenant_type: str = "hospital",
    admin_capabilities: list[str] | None = None,
    dpdp_consent_required: bool = False,
) -> Hospital:
    """Onboarding wizard's entry point (SPEC Section 12.1, Phase 10). Raises
    db.connection.IntegrityError if whatsapp_phone_number_id is already used by
    another hospital -- db/schema.sql's UNIQUE constraint is the actual guard
    against breaking Phase 9's per-message routing, not application logic;
    callers (admin/onboarding.py) are responsible for catching it.

    data_tier (Section 12.6, Step 0 of the wizard as of Section 14.6's
    reorder): "tier1" (default, this product's own database), "tier2"
    (external_api_base_url/external_api_key are only stored here -- no
    connector logic reads them yet), or "tier3" (direct DB connection, not
    self-serve -- neither field is meaningful for it).

    portal_password (Section 12.7): plaintext in, hashed before storage --
    optional at onboarding time (a hospital can set it later via the edit
    form); left unset, the bookings portal simply has no way to log into that
    hospital yet.

    enabled_features (Section 14.5): the set of patient-facing capabilities
    this hospital's WhatsApp number offers (e.g. ["booking","reschedule",
    "cancel","faq"]) -- flows.py's IDLE main menu shows only these. Replaces
    the earlier single-value flow_type (Section 14.1); defaults to an empty
    list (no capabilities enabled) rather than guessing "booking", since an
    empty set is a safe, honest default a caller has to deliberately override,
    not a value that quietly implies functionality nothing configured yet.

    feature_labels/closing_message_text/business_hours_text/default_language/
    language_prompt_enabled/session_timeout_minutes (Section 12.13): self-serve
    bot customization, all optional -- see db/schema.sql's column comments.
    Every one defaults to "unset" (None, or True for language_prompt_enabled)
    here too, same reasoning as enabled_features above: a hospital that never
    touches its settings page keeps the exact fixed default behavior.

    tenant_type/admin_capabilities (tenant-capability-gating-plan.md):
    admin_capabilities is stored EXACTLY as given -- this function doesn't
    resolve DEFAULT_CAPABILITIES_BY_TYPE itself (that policy decision lives
    in backend/portal/capabilities.py, imported by the onboarding API layer
    that actually calls this with an already-resolved list), same
    "repository function stores what it's told, doesn't compute defaults"
    precedent enabled_features already sets. None stores NULL (falls back
    to the type default at read time, backend/portal/capabilities.py's
    get_capabilities())."""
    conn = get_connection()
    offsets_json = json_lib.dumps(reminder_offsets_hours or [24])
    features_json = json_lib.dumps(enabled_features or [])
    feature_labels_json = json_lib.dumps(feature_labels or {})
    admin_capabilities_json = json_lib.dumps(admin_capabilities) if admin_capabilities is not None else None
    portal_password_hash = hash_portal_password(portal_password) if portal_password else None
    cur = conn.execute(
        "INSERT INTO hospitals (name, whatsapp_phone_number_id, meta_access_token_ref, app_secret_ref, "
        "timezone, welcome_message_text, reminder_offsets_hours, reminder_template_name, "
        "data_tier, external_api_base_url, external_api_key, portal_password_hash, enabled_features, "
        "feature_labels, closing_message_text, business_hours_text, default_language, "
        "language_prompt_enabled, session_timeout_minutes, require_patient_confirmation, privacy_notice_text, "
        "tenant_type, admin_capabilities, dpdp_consent_required) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (name, whatsapp_phone_number_id, access_token, app_secret, timezone,
         welcome_message_text, offsets_json, reminder_template_name,
         data_tier, external_api_base_url, external_api_key, portal_password_hash, features_json,
         feature_labels_json, closing_message_text, business_hours_text, default_language,
         int(language_prompt_enabled), session_timeout_minutes,
         bool(require_patient_confirmation), privacy_notice_text, tenant_type, admin_capabilities_json,
         bool(dpdp_consent_required)),
    )
    new_id = cur.fetchone()["id"]
    # Appointment type step (WhatsApp flow alignment): every new hospital
    # gets the same fixed catalog db/init_db.py's own startup backfill seeds
    # for pre-existing hospitals (DEFAULT_APPOINTMENT_TYPES is the single
    # source of truth both share) -- without this, a hospital onboarded
    # after startup (the real self-serve onboarding wizard path, and any
    # test that creates a hospital mid-run) would have ZERO appointment
    # types and booking would have nothing to offer at that step.
    for sort_order, appt_type in enumerate(DEFAULT_APPOINTMENT_TYPES):
        conn.execute(
            "INSERT INTO appointment_types "
            "(id, hospital_id, label, requires_consent, requires_doctor_selection, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                appt_type["id"], new_id, appt_type["label"], appt_type["requires_consent"],
                appt_type["requires_doctor_selection"], sort_order,
            ),
        )
    conn.commit()
    return get_hospital(new_id)


def update_hospital(
    hospital_id: int,
    name: str,
    whatsapp_phone_number_id: str,
    access_token: str | None = None,
    app_secret: str | None = None,
    timezone: str = "UTC",
    welcome_message_text: str | None = None,
    reminder_offsets_hours: list[float] | None = None,
    reminder_template_name: str | None = None,
    data_tier: str = "tier1",
    external_api_base_url: str | None = None,
    external_api_key: str | None = None,
    portal_password_hash: str | None = None,
    enabled_features: list[str] | None = None,
    feature_labels: dict[str, str] | None = None,
    closing_message_text: str | None = None,
    business_hours_text: str | None = None,
    default_language: str | None = None,
    language_prompt_enabled: bool = True,
    session_timeout_minutes: int | None = None,
    require_patient_confirmation: bool = False,
    privacy_notice_text: str | None = None,
    tenant_type: str = "hospital",
    admin_capabilities: list[str] | None = None,
    dpdp_consent_required: bool = False,
) -> Hospital:
    """admin/onboarding.py's tenant edit form -- the only way to correct an
    already-onboarded hospital's stored values (there's no way to change
    departments/doctors here, only the hospitals row itself). Raises
    db.connection.IntegrityError if whatsapp_phone_number_id is changed to a
    value another hospital already uses -- same UNIQUE constraint create_hospital()
    relies on; a hospital keeping its own existing phone_number_id unchanged
    never conflicts with itself. Callers (admin/onboarding.py) are responsible
    for catching it, same as create_hospital().

    portal_password_hash takes an ALREADY-HASHED value (or the hospital's
    existing one, to leave it unchanged) -- unlike create_hospital(), which
    takes a raw password, because the edit route needs to decide whether a
    blank submitted field means "keep current hash" *before* this function
    ever sees it (hashing here would turn a blank field into a real password).

    Deliberately does NOT touch _wa_clients (core/main.py's per-hospital
    WhatsAppClient cache) -- it can't, from here; a hospital whose credentials
    just changed keeps using its OLD cached client until the process restarts.
    See core/main.py's _wa_clients comment and the post-edit confirmation page.

    enabled_features (Section 14.5) defaults to an empty list like
    create_hospital(), but every caller (admin/onboarding.py's edit-tenant
    route, portal.py's settings route) passes the hospital's own current
    value through explicitly -- neither exposes a way to CHANGE which
    features are enabled yet, so an edit to something else must never
    silently reset a tenant's real feature set back to empty.

    feature_labels/closing_message_text/business_hours_text/default_language/
    language_prompt_enabled/session_timeout_minutes (Section 12.13): same
    "every caller passes the hospital's own current value through explicitly"
    discipline as enabled_features -- ONLY portal/routes/settings.py's settings save
    endpoint actually changes these; every other caller (admin edit-tenant
    forms, portal.py's own settings route for the still-unmigrated fields)
    passes the hospital's existing values straight through so an unrelated
    edit can never silently wipe a tenant's customizations back to defaults.

    tenant_type/admin_capabilities (tenant-capability-gating-plan.md): same
    "every caller passes the hospital's own current value through
    explicitly" discipline -- only admin/tenants_api.py's tenant-edit
    endpoint actually changes these (the tenant/platform admin flipping a
    clinic's capability set); every other caller passes the hospital's
    existing tenant_type/admin_capabilities straight through."""
    conn = get_connection()
    offsets_json = json_lib.dumps(reminder_offsets_hours or [24])
    features_json = json_lib.dumps(enabled_features or [])
    feature_labels_json = json_lib.dumps(feature_labels or {})
    admin_capabilities_json = json_lib.dumps(admin_capabilities) if admin_capabilities is not None else None
    conn.execute(
        "UPDATE hospitals SET name = ?, whatsapp_phone_number_id = ?, meta_access_token_ref = ?, "
        "app_secret_ref = ?, timezone = ?, welcome_message_text = ?, reminder_offsets_hours = ?, "
        "reminder_template_name = ?, data_tier = ?, external_api_base_url = ?, external_api_key = ?, "
        "portal_password_hash = ?, enabled_features = ?, feature_labels = ?, closing_message_text = ?, "
        "business_hours_text = ?, default_language = ?, language_prompt_enabled = ?, "
        "session_timeout_minutes = ?, require_patient_confirmation = ?, privacy_notice_text = ?, "
        "tenant_type = ?, admin_capabilities = ?, dpdp_consent_required = ? WHERE id = ?",
        (name, whatsapp_phone_number_id, access_token, app_secret, timezone,
         welcome_message_text, offsets_json, reminder_template_name,
         data_tier, external_api_base_url, external_api_key, portal_password_hash, features_json,
         feature_labels_json, closing_message_text, business_hours_text, default_language,
         int(language_prompt_enabled), session_timeout_minutes,
         bool(require_patient_confirmation), privacy_notice_text, tenant_type, admin_capabilities_json,
         bool(dpdp_consent_required), hospital_id),
    )
    conn.commit()
    return get_hospital(hospital_id)


