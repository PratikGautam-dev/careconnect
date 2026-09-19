# portal/routes/roles.py
"""Roles & Permissions admin UI's backend -- lets an
admin create/rename/delete their own hospital's roles, and view/edit each
role's per-page permission grid. Gated by require_permission(principal,
"roles", ...) itself, not a hardcoded "only role == admin" check -- admin
gets view+write on PAGE_ROLES by default (portal/permissions.py's
DEFAULT_PERMISSIONS_BY_ROLE_KIND), but this page is itself
editable like every other page, so a hospital could in principle grant a
receptionist read access to it too."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from portal.deps import get_current_staff, require_permission
from portal.permission_cache import invalidate, invalidate_staff
from portal.permissions import ALL_PAGES, get_permission_matrix

router = APIRouter()


@router.get("/api/portal/roles")
async def list_roles(authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "view")
    if forbidden:
        return forbidden
    return JSONResponse({"roles": db.list_roles(principal.hospital.id)})


class CreateRolePayload(BaseModel):
    name: str = ""
    description: str = ""
    clone_from_role_id: int | None = None


@router.post("/api/portal/roles")
async def create_role(payload: CreateRolePayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "write")
    if forbidden:
        return forbidden

    name = payload.name.strip()
    if not name:
        return JSONResponse({"error": "Name is required."}, status_code=400)
    if payload.clone_from_role_id is not None and db.get_role(principal.hospital.id, payload.clone_from_role_id) is None:
        return JSONResponse({"error": "Choose a valid role to clone from."}, status_code=400)

    try:
        role = db.create_role(
            principal.hospital.id, name, payload.description.strip(),
            clone_from_role_id=payload.clone_from_role_id,
        )
    except db.IntegrityError:
        return JSONResponse({"error": f'A role named "{name}" already exists at this hospital.'}, status_code=400)

    invalidate(principal.hospital.id)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "roles.create",
        entity_type="role", entity_id=str(role["id"]), after={"name": name},
    )
    return JSONResponse({"role": role}, status_code=201)


class UpdateRolePayload(BaseModel):
    name: str | None = None
    description: str | None = None


@router.patch("/api/portal/roles/{role_id}")
async def update_role(role_id: int, payload: UpdateRolePayload, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "write")
    if forbidden:
        return forbidden

    role = db.get_role(principal.hospital.id, role_id)
    if role is None:
        return JSONResponse({"error": "No such role."}, status_code=404)

    name = payload.name.strip() if payload.name is not None else None
    if name is not None and not name:
        return JSONResponse({"error": "Name is required."}, status_code=400)

    try:
        updated = db.update_role(
            principal.hospital.id, role_id, name=name, description=payload.description,
        )
    except db.IntegrityError:
        return JSONResponse({"error": f'A role named "{name}" already exists at this hospital.'}, status_code=400)

    invalidate(principal.hospital.id)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "roles.update",
        entity_type="role", entity_id=str(role_id), after=payload.model_dump(exclude_none=True),
    )
    return JSONResponse({"role": updated})


@router.delete("/api/portal/roles/{role_id}")
async def delete_role(role_id: int, authorization: str | None = Header(default=None)):
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "write")
    if forbidden:
        return forbidden

    role = db.get_role(principal.hospital.id, role_id)
    if role is None:
        return JSONResponse({"error": "No such role."}, status_code=404)
    if role["is_protected"]:
        return JSONResponse({"error": "The Admin role is reserved and can't be deleted."}, status_code=400)
    active_count = db.count_staff_with_role(principal.hospital.id, role_id, active_only=True)
    if active_count > 0:
        return JSONResponse(
            {"error": f"{active_count} active staff member(s) are still assigned to this role."}, status_code=400,
        )

    db.delete_role(principal.hospital.id, role_id)
    invalidate(principal.hospital.id)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "roles.delete",
        entity_type="role", entity_id=str(role_id), before={"name": role["name"]},
    )
    return JSONResponse({"ok": True})


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
    role_id: int
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

    valid_role_ids = {r["id"] for r in db.list_roles(principal.hospital.id)}
    errors = []
    rows = []
    for update in payload.updates:
        if update.role_id not in valid_role_ids:
            errors.append(f'Unrecognized role "{update.role_id}".')
            continue
        if update.page_key not in ALL_PAGES:
            errors.append(f'Unrecognized page "{update.page_key}".')
            continue
        rows.append({
            "role_id": update.role_id, "page_key": update.page_key,
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
        after={"updates": [f'{r["role_id"]}.{r["page_key"]}' for r in rows]},
    )
    return JSONResponse({"permissions": get_permission_matrix(principal.hospital.id)})


@router.get("/api/portal/roles/{role_id}/users")
async def get_role_users(role_id: int, authorization: str | None = Header(default=None)):
    """User-level permission overrides (see the approved plan) -- the
    "Users on this role" panel's own data source: every staff member
    currently on this role, plus each of their own sparse override rows
    (the frontend already has this role's own default matrix from GET
    /api/portal/roles, so it overlays these client-side rather than this
    route re-resolving an "effective" matrix per user)."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "view")
    if forbidden:
        return forbidden

    if db.get_role(principal.hospital.id, role_id) is None:
        return JSONResponse({"error": "No such role."}, status_code=404)

    staff = db.list_staff_for_role(principal.hospital.id, role_id)
    overrides_by_staff = db.get_overrides_for_role(principal.hospital.id, role_id)
    return JSONResponse({
        "users": [
            {
                "staff_id": s["staff_id"], "name": s["name"], "email": s["email"], "is_active": s["is_active"],
                "overrides": [
                    {"page_key": o["page_key"], "view": o["can_view"], "write": o["can_write"], "delete": o["can_delete"]}
                    for o in overrides_by_staff.get(s["staff_id"], [])
                ],
            }
            for s in staff
        ],
    })


class StaffPermissionOverrideUpdate(BaseModel):
    page_key: str
    view: bool | None = None
    write: bool | None = None
    delete: bool | None = None


class StaffPermissionOverridesPayload(BaseModel):
    updates: list[StaffPermissionOverrideUpdate] = []


@router.put("/api/portal/staff/{staff_id}/permissions")
async def update_staff_permission_overrides(
    staff_id: int, payload: StaffPermissionOverridesPayload, authorization: str | None = Header(default=None),
):
    """Sets/clears one staff member's own permission overrides -- each of
    view/write/delete is explicit true/false (an override) or null ("clear
    it, inherit whatever this person's role says"). Gated on "roles" write
    access, same as editing a role's own grid -- overriding one person's
    access is itself an access-control admin action."""
    principal = get_current_staff(authorization)
    if principal is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_permission(principal, "roles", "write")
    if forbidden:
        return forbidden

    target = db.get_staff_user_by_id(staff_id)
    if target is None or target["hospital_id"] != principal.hospital.id:
        return JSONResponse({"error": "Staff member not found."}, status_code=404)

    errors = []
    rows = []
    for update in payload.updates:
        if update.page_key not in ALL_PAGES:
            errors.append(f'Unrecognized page "{update.page_key}".')
            continue
        rows.append(update)
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)
    if not rows:
        return JSONResponse({"errors": ["No permission updates were provided."]}, status_code=400)

    for update in rows:
        db.upsert_staff_override(
            principal.hospital.id, staff_id, update.page_key, update.view, update.write, update.delete,
        )
    invalidate_staff(principal.hospital.id, staff_id)
    db.record_audit_log(
        "portal", principal.hospital.id, f"{principal.name} <staff:{principal.staff_id}>", "staff.permissions_override",
        entity_type="staff_permission_overrides", entity_id=str(staff_id),
        after={"updates": [u.page_key for u in rows]},
    )
    return JSONResponse({"overrides": db.get_staff_overrides(principal.hospital.id, staff_id)})
