# portal/routes/roles.py
"""Roles & Permissions admin UI's backend (docs/rbac-redis-plan.md) -- lets
an admin view and edit their own hospital's per-role page permission grid.
Gated by require_permission(principal, "roles", ...) itself, not a hardcoded
"only role == admin" check -- admin gets view+write on PAGE_ROLES by default
(portal/permissions.py's DEFAULT_PERMISSIONS_BY_ROLE), but per the plan this
page is itself editable like every other page, so a hospital could in
principle grant a receptionist read access to it too."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from portal.deps import get_current_staff, require_permission
from portal.permission_cache import invalidate
from portal.permissions import ALL_PAGES, get_permission_matrix

router = APIRouter()


@router.get("/api/portal/roles/permissions")
async def get_permissions(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "view")
    if forbidden:
        return forbidden
    return JSONResponse({"permissions": get_permission_matrix(principal.hospital.id)})


class PermissionUpdate(BaseModel):
    role: str
    page_key: str
    can_view: bool = False
    can_write: bool = False
    can_delete: bool = False


class PermissionsUpdatePayload(BaseModel):
    updates: list[PermissionUpdate] = []


@router.put("/api/portal/roles/permissions")
async def update_permissions(payload: PermissionsUpdatePayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "write")
    if forbidden:
        return forbidden

    valid_roles = {"admin", "receptionist", "doctor"}
    errors = []
    rows = []
    for update in payload.updates:
        if update.role not in valid_roles:
            errors.append(f'Unrecognized role "{update.role}".')
            continue
        if update.page_key not in ALL_PAGES:
            errors.append(f'Unrecognized page "{update.page_key}".')
            continue
        rows.append({
            "role": update.role, "page_key": update.page_key,
            "can_view": update.can_view, "can_write": update.can_write, "can_delete": update.can_delete,
        })
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)
    if not rows:
        return JSONResponse({"errors": ["No permission updates were provided."]}, status_code=400)

    db.upsert_role_permissions(principal.hospital.id, rows)
    # Redis pub/sub invalidation (portal/permission_cache.py) -- makes this
    # edit take effect immediately for every already-logged-in staff member
    # at this hospital, on every worker process, not just the one that
    # served this request (main.py's startup subscriber is what's listening
    # on the other processes).
    invalidate(principal.hospital.id)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "roles.update_permissions",
        entity_type="role_permissions", entity_id=str(principal.hospital.id),
        after={"updates": [f'{r["role"]}.{r["page_key"]}' for r in rows]},
    )
    return JSONResponse({"permissions": get_permission_matrix(principal.hospital.id)})
