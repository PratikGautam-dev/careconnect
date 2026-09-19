import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

export type Action = "view" | "write" | "delete";
export type PagePerms = Record<Action, boolean>;
// Dynamic-roles migration: keyed by role_id (int), not a fixed role-name
// union -- a hospital's own admin-defined roles, unbounded.
export type Matrix = Record<number, Record<string, PagePerms>>;

export type Role = {
  id: number;
  name: string;
  description: string;
  is_protected: boolean;
  staff_count: number;
  active_staff_count: number;
};

// User-level permission overrides -- a second, sparse layer on top of the
// role matrix above; each action is true/false (an explicit override) or
// null (no opinion, inherit the role's own value for that cell).
export type OverrideCell = { view: boolean | null; write: boolean | null; delete: boolean | null };
export type RoleUserOverride = OverrideCell & { page_key: string };
export type RoleUser = {
  staff_id: number;
  name: string;
  email: string;
  is_active: boolean;
  overrides: RoleUserOverride[];
};

/** Loads + owns every mutation on the /portal/settings/roles page -- the
 * roles list itself (create/rename/delete live in useRoleManagement.ts,
 * this hook is read + the permission matrix's one optimistic-update PUT per
 * checkbox toggle, rolled back on failure). Per-role staff counts (for the
 * stat tiles/Role Management table) come straight off each role's own
 * staff_count/active_staff_count (db/repositories/roles.py's list_roles())
 * -- no separate client-side merge against the staff/doctors lists needed,
 * since role membership is counted server-side regardless of whether a
 * member happens to be linked to a doctor profile. */
export function usePortalRoles(canView: boolean) {
  const router = useRouter();
  const [roles, setRoles] = useState<Role[]>([]);
  const [matrix, setMatrix] = useState<Matrix | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Tracks the single cell currently in flight, e.g. "3:staff:write", so
  // only that checkbox shows a pending state while its PUT resolves.
  const [savingCell, setSavingCell] = useState<string | null>(null);

  const loadRoles = useCallback(async (): Promise<Role[]> => {
    const result = await staffFetch("/api/portal/roles");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return [];
    }
    const fetched = (result.data as { roles: Role[] }).roles;
    setRoles(fetched);
    return fetched;
  }, [router]);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/roles/permissions");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    // JSON object keys are always strings -- re-cast back to number so
    // matrix[role.id] lookups (role.id is a number) actually hit.
    const raw = (result.data as { permissions: Record<string, Record<string, PagePerms>> })
      .permissions;
    setMatrix(
      Object.fromEntries(Object.entries(raw).map(([roleId, pages]) => [Number(roleId), pages])),
    );
  }, [router]);

  useEffect(() => {
    if (canView) {
      load();
      loadRoles();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView, load, loadRoles]);

  async function handleToggle(roleId: number, pageKey: string, action: Action, next: boolean) {
    if (!matrix) return;
    const cellKey = `${roleId}:${pageKey}:${action}`;
    const prevCell = matrix[roleId][pageKey];
    const nextCell = { ...prevCell, [action]: next };
    setMatrix({ ...matrix, [roleId]: { ...matrix[roleId], [pageKey]: nextCell } });
    setSavingCell(cellKey);
    const result = await staffFetch("/api/portal/roles/permissions", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      // Backend contract (portal/routes/roles.py's PermissionsUpdatePayload)
      // is a batch of updates, even for a single-cell toggle like this one --
      // an earlier version of this call sent the fields flat/unwrapped,
      // which parsed fine (Pydantic ignores unknown fields) but always hit
      // the route's "no updates provided" 400, since `updates` defaulted to
      // an empty list.
      body: JSON.stringify({
        updates: [
          {
            role_id: roleId,
            page_key: pageKey,
            can_view: nextCell.view,
            can_write: nextCell.write,
            can_delete: nextCell.delete,
          },
        ],
      }),
    });
    setSavingCell(null);
    if (!result.ok) {
      // Roll back on failure -- optimistic update kept the UI responsive
      // (this can be a lot of clicking through a wide grid) but must not
      // silently drift from what the backend actually has stored.
      setMatrix({ ...matrix, [roleId]: { ...matrix[roleId], [pageKey]: prevCell } });
      if (result.unauthorized) {
        router.push("/portal/login");
      } else {
        setError(result.error);
        toast.error("Couldn't update permission", result.error);
      }
    }
  }

  /** Add Role modal's submit -- optionally cloning an existing role's
   * actual current permissions (not factory defaults) as a starting point;
   * a role created with no clone source starts with zero access anywhere
   * (fail-closed, portal/permissions.py's own documented behavior).
   * Returns an error string on failure, null on success. */
  async function createRole(
    name: string,
    description: string,
    cloneFromRoleId: number | null,
  ): Promise<string | null> {
    const result = await staffFetch("/api/portal/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description, clone_from_role_id: cloneFromRoleId }),
    });
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      return result.unauthorized ? null : result.error;
    }
    await loadRoles();
    await load();
    return null;
  }

  /** Rename/edit-description for an existing role -- partial update, only
   * the fields actually changed need to be passed. */
  async function updateRole(
    roleId: number,
    updates: { name?: string; description?: string },
  ): Promise<string | null> {
    const result = await staffFetch(`/api/portal/roles/${roleId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      return result.unauthorized ? null : result.error;
    }
    await loadRoles();
    return null;
  }

  /** Blocked server-side (400) if this role is reserved (the Admin role) or
   * has active staff assigned -- the error message names the specific
   * reason/count. */
  async function deleteRole(roleId: number): Promise<string | null> {
    const result = await staffFetch(`/api/portal/roles/${roleId}`, { method: "DELETE" });
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      return result.unauthorized ? null : result.error;
    }
    await loadRoles();
    return null;
  }

  /** "Users on this role" panel's own data source (opened lazily from the
   * per-role permissions Dialog, not prefetched for every role up front). */
  const loadRoleUsers = useCallback(
    async (roleId: number): Promise<RoleUser[]> => {
      const result = await staffFetch(`/api/portal/roles/${roleId}/users`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        else setError(result.error);
        return [];
      }
      return (result.data as { users: RoleUser[] }).users;
    },
    [router],
  );

  /** Sets/clears one staff member's own override for one page -- `next` is
   * that page's FULL {view,write,delete} cell (each true/false/null), not
   * just the one action the admin just clicked, since the backend replaces
   * the whole triple per page (same "always send the full cell" shape
   * handleToggle above already uses for role permissions). Returns an
   * error string on failure, null on success. */
  async function updateStaffOverride(
    staffId: number,
    pageKey: string,
    next: OverrideCell,
  ): Promise<string | null> {
    const result = await staffFetch(`/api/portal/staff/${staffId}/permissions`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ updates: [{ page_key: pageKey, ...next }] }),
    });
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      return result.unauthorized ? null : result.error;
    }
    return null;
  }

  return {
    roles,
    loadRoles,
    matrix,
    error,
    savingCell,
    handleToggle,
    createRole,
    updateRole,
    deleteRole,
    loadRoleUsers,
    updateStaffOverride,
  };
}
