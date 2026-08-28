# db/repositories/audit_logs.py
"""Two-level audit trail (tenant-capability-gating-plan.md's follow-up):
'platform_admin' entries record TENANTS_ADMIN_SECRET-gated changes to a
tenant (admin/tenants_api.py); 'portal' entries record an authenticated
tenant's own staff-portal mutations (doctor/department CRUD, appointment-type
toggles, settings updates). See db/orm_models.py's AuditLog / db/schema.sql's
audit_logs table for the column shapes this wraps.

Single source of truth for the redaction list -- before_value/after_value are
JSON of CHANGED fields only (never a full row), and any of these keys is
logged as the literal string "<changed>", never its actual value, since this
table is read by platform operators and (for 'portal' rows) by tenant staff
who must never be able to recover a credential from history."""
import json
from datetime import datetime

from sqlalchemy import select

from db.connection import get_session
from db.orm_models import AuditLog

_REDACTED_KEYS = {"access_token", "app_secret", "portal_password_hash", "external_api_key"}


def _redact(fields: dict | None) -> str | None:
    if fields is None:
        return None
    safe = {k: ("<changed>" if k in _REDACTED_KEYS else v) for k, v in fields.items()}
    return json.dumps(safe)


def record_audit_log(
    actor_level: str,
    hospital_id: int | None,
    actor_label: str,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """actor_level must be 'platform_admin' or 'portal' (db/schema.sql's own
    CHECK constraint is the real guard; this isn't re-validated here since
    both call sites pass a hardcoded literal, never a caller-supplied
    value). before/after should be a dict of only the fields that actually
    changed, not the full before/after row -- callers are responsible for
    diffing first, this function only handles redaction + JSON encoding."""
    session = get_session()
    session.add(AuditLog(
        actor_level=actor_level,
        hospital_id=hospital_id,
        actor_label=actor_label,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=_redact(before),
        after_value=_redact(after),
        # Set explicitly, not left to the DB's server_default -- the ORM
        # INSERT includes every mapped column (as an explicit NULL) unless
        # told otherwise, same reason every other TEXT timestamp column in
        # this codebase is stamped in Python (datetime.now().isoformat()),
        # never left to a Postgres-side default.
        created_at=datetime.now().isoformat(),
    ))
    session.commit()


def get_audit_logs(
    hospital_id: int | None = None, actor_level: str | None = None, limit: int = 100
) -> list[dict]:
    """Newest first. hospital_id=None + actor_level=None returns everything
    (platform-admin cross-tenant view); a portal-facing route should always
    pass both its own hospital_id and actor_level='portal' so a tenant can
    never see another tenant's rows or platform-only actions."""
    session = get_session()
    query = select(AuditLog)
    if hospital_id is not None:
        query = query.where(AuditLog.hospital_id == hospital_id)
    if actor_level is not None:
        query = query.where(AuditLog.actor_level == actor_level)
    query = query.order_by(AuditLog.id.desc()).limit(limit)
    rows = session.execute(query).scalars().all()
    return [
        {
            "id": r.id,
            "actor_level": r.actor_level,
            "hospital_id": r.hospital_id,
            "actor_label": r.actor_label,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "before_value": json.loads(r.before_value) if r.before_value else None,
            "after_value": json.loads(r.after_value) if r.after_value else None,
            # Defensive: this column is TEXT (db/init_db.py self-heals any
            # environment where it isn't), but a real datetime slipping
            # through here would otherwise crash JSON serialization at the
            # route layer with an opaque 500 -- cheap enough to guard here.
            "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime) else r.created_at,
        }
        for r in rows
    ]
