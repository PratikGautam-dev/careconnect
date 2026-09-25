"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  KeyRound,
  Minus,
  Plus,
  ScrollText,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { cn } from "@/lib/cn";
import { toast } from "@/lib/toast";
import { usePermission, useStaffSession } from "@/lib/staffAuth";
import {
  usePortalRoles,
  type OverrideCell,
  type Role,
  type RoleUser,
} from "@/hooks/usePortalRoles";
import {
  createRoleColumns,
  createRoleManagementColumns,
  createStaffOverrideColumns,
} from "./_components/role-columns";

const EMPTY_CELL: OverrideCell = { view: null, write: null, delete: null };

const PAGE_KEYS = [
  "dashboard",
  "appointments",
  "daycare_appointments",
  "diagnostic_appointments",
  "patients",
  "schedule",
  "doctors",
  "diagnostic_tests",
  "messages",
  "settings",
  "staff",
  "roles",
  "leave_requests",
  "holiday_application",
  "attendance",
  "check_in_out",
  "report-review",
  "report-analytics",
];
const PAGE_LABEL: Record<string, string> = {
  dashboard: "Dashboard",
  appointments: "Doctor Appointments",
  daycare_appointments: "Daycare Appointments",
  diagnostic_appointments: "Lab & Diagnostic Appointments",
  patients: "Patients",
  schedule: "Schedule",
  doctors: "Doctors",
  diagnostic_tests: "Diagnostic Tests",
  messages: "Messages",
  settings: "Settings",
  staff: "Staff",
  roles: "Roles & Permissions",
  leave_requests: "Leave Requests",
  holiday_application: "Holiday Application",
  attendance: "Attendance",
  check_in_out: "Check-in / Check-out",
  "report-review": "Report Review",
  "report-analytics": "Report Analytics",
};

type RoleFormState = { name: string; description: string; cloneFromRoleId: string };
const EMPTY_ROLE_FORM: RoleFormState = { name: "", description: "", cloneFromRoleId: "" };

export default function RolesPermissionsPage() {
  // null on the server and on the client's first render, so
  // PortalShell/PortalSidebar avoid a hydration mismatch against the
  // server-rendered "Hospital" placeholder.
  const session = useStaffSession();
  const canView = usePermission("roles", "view");
  const canWrite = usePermission("roles", "write");

  const {
    roles,
    matrix,
    error,
    savingCell,
    handleToggle,
    createRole,
    updateRole,
    deleteRole,
    loadRoleUsers,
    updateStaffOverride,
  } = usePortalRoles(canView);
  const [editingRoleId, setEditingRoleId] = useState<number | null>(null);

  // "Manage Users" -- its own top-level action beside "Edit Permissions",
  // not nested inside it. Loaded lazily the moment this dialog opens, not
  // prefetched for every role up front. overrideStaffId picks which user's
  // own override grid (a second, nested Dialog) is currently open.
  const [manageUsersRoleId, setManageUsersRoleId] = useState<number | null>(null);
  const [overrideStaffId, setOverrideStaffId] = useState<number | null>(null);
  const [savingOverrideCell, setSavingOverrideCell] = useState<string | null>(null);

  // Add Role / Rename share one modal + form shape -- `renameTarget` null
  // means "Add Role" (POST), non-null means "Rename" (PATCH that role).
  const [roleFormOpen, setRoleFormOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<Role | null>(null);
  const [roleForm, setRoleForm] = useState<RoleFormState>(EMPTY_ROLE_FORM);
  const [roleFormError, setRoleFormError] = useState<string | null>(null);
  const [savingRoleForm, setSavingRoleForm] = useState(false);

  // Loaded lazily the moment "Manage Users" opens -- React-Query-backed
  // (queryKey includes manageUsersRoleId) instead of a hand-rolled
  // fetch-inside-a-useEffect, so this doesn't trip react-hooks/
  // set-state-in-effect (see useDoctorDashboard.ts for the same reasoning
  // applied elsewhere).
  const queryClient = useQueryClient();
  const roleUsersQueryKey = ["portal-role-users", manageUsersRoleId] as const;
  const { data: roleUsersData, isFetching: loadingRoleUsers } = useQuery({
    queryKey: roleUsersQueryKey,
    enabled: manageUsersRoleId !== null,
    queryFn: () => loadRoleUsers(manageUsersRoleId as number),
  });
  const roleUsers = manageUsersRoleId === null ? null : (roleUsersData ?? null);

  // Resets the nested per-staff override dialog's target whenever the
  // "Manage Users" dialog closes (manageUsersRoleId -> null) -- adjusted
  // directly in the render body (comparing against the previous
  // manageUsersRoleId) rather than in an effect, per React's own
  // "Adjusting some state when a prop changes" guide. Mirrors the original
  // effect's own `if (manageUsersRoleId === null) setOverrideStaffId(null)`
  // branch exactly -- switching between two already-open non-null role ids
  // deliberately does NOT reset it, same as before.
  const [prevManageUsersRoleId, setPrevManageUsersRoleId] = useState(manageUsersRoleId);
  if (manageUsersRoleId !== prevManageUsersRoleId) {
    setPrevManageUsersRoleId(manageUsersRoleId);
    if (manageUsersRoleId === null) setOverrideStaffId(null);
  }

  if (!canView) {
    return (
      <PortalShell hospital={session?.hospital || null} active="roles">
        <p className="text-ink-400 text-[13px]">
          You don&apos;t have access to Roles &amp; Permissions.
        </p>
      </PortalShell>
    );
  }

  const totalPermissionCells = roles.length * PAGE_KEYS.length;
  const totalUsers = roles.reduce((sum, r) => sum + r.staff_count, 0);
  const activeRoleCount = roles.filter((r) => r.active_staff_count > 0).length;
  const editingRole = roles.find((r) => r.id === editingRoleId) || null;
  const manageUsersRole = roles.find((r) => r.id === manageUsersRoleId) || null;

  function openAddRole() {
    setRenameTarget(null);
    setRoleForm(EMPTY_ROLE_FORM);
    setRoleFormError(null);
    setRoleFormOpen(true);
  }

  function openRename(role: Role) {
    setRenameTarget(role);
    setRoleForm({ name: role.name, description: role.description, cloneFromRoleId: "" });
    setRoleFormError(null);
    setRoleFormOpen(true);
  }

  async function handleRoleFormSubmit(e: React.FormEvent) {
    e.preventDefault();
    const name = roleForm.name.trim();
    if (!name) {
      setRoleFormError("Name is required.");
      return;
    }
    setSavingRoleForm(true);
    setRoleFormError(null);
    const err = renameTarget
      ? await updateRole(renameTarget.id, { name, description: roleForm.description.trim() })
      : await createRole(
          name,
          roleForm.description.trim(),
          roleForm.cloneFromRoleId ? Number(roleForm.cloneFromRoleId) : null,
        );
    setSavingRoleForm(false);
    if (err) {
      setRoleFormError(err);
      return;
    }
    toast.success(renameTarget ? "Role updated" : "Role created");
    setRoleFormOpen(false);
  }

  async function handleDeleteRole(role: Role) {
    if (!window.confirm(`Delete the "${role.name}" role? This can't be undone.`)) return;
    const err = await deleteRole(role.id);
    if (err) toast.error("Couldn't delete role", err);
    else toast.success("Role deleted");
  }

  /** One cell of one user's override grid changed -- `next` is that page's
   * FULL {view,write,delete} cell, all-null meaning "cleared, back to
   * inheriting the role." Updates the local roleUsers list on success so
   * the grid reflects it immediately without a full re-fetch. */
  async function handleOverrideChange(staffId: number, pageKey: string, next: OverrideCell) {
    const cellKey = `${staffId}:${pageKey}`;
    setSavingOverrideCell(cellKey);
    const err = await updateStaffOverride(staffId, pageKey, next);
    setSavingOverrideCell(null);
    if (err) {
      toast.error("Couldn't update permission", err);
      return;
    }
    const isCleared = next.view === null && next.write === null && next.delete === null;
    queryClient.setQueryData<RoleUser[]>(
      roleUsersQueryKey,
      (prev) =>
        prev &&
        prev.map((u) => {
          if (u.staff_id !== staffId) return u;
          const rest = u.overrides.filter((o) => o.page_key !== pageKey);
          return { ...u, overrides: isCleared ? rest : [...rest, { page_key: pageKey, ...next }] };
        }),
    );
  }

  const roleManagementColumns = createRoleManagementColumns({
    canManage: canWrite,
    userCountFor: (roleId) => roles.find((r) => r.id === roleId)?.staff_count || 0,
    onEditPermissions: setEditingRoleId,
    onManageUsers: setManageUsersRoleId,
    onRename: openRename,
    onDelete: handleDeleteRole,
  });

  return (
    <PortalShell hospital={session?.hospital || null} active="roles">
      <PageHeader
        title="Roles & Permissions"
        description="Manage user roles, permissions and access across the portal."
      />

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Total Roles"
          value={roles.length}
          deltaPct={null}
          hint="Roles at this hospital"
          icon={Users}
        />
        <StatTile
          label="Total Users"
          value={totalUsers}
          deltaPct={null}
          hint="Across all roles"
          icon={UserRound}
        />
        <StatTile
          label="Active Roles"
          value={activeRoleCount}
          deltaPct={null}
          hint={`of ${roles.length} have an active user`}
          icon={ShieldCheck}
          tint="success"
        />
        <StatTile
          label="Total Permissions"
          value={totalPermissionCells}
          deltaPct={null}
          hint="Role x module combinations"
          icon={KeyRound}
        />
      </div>

      {!matrix ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-[1fr_360px]">
          <div className="space-y-space-4">
            <Card className="p-space-4">
              <div className="mb-space-3">
                <h3 className="text-label text-ink-900 font-bold">Role Management</h3>
                <p className="text-hint">
                  {roles.length} role{roles.length === 1 ? "" : "s"} at this hospital.
                  {!canWrite && " You have view-only access."}
                </p>
              </div>
              <DataTable
                columns={roleManagementColumns}
                data={roles}
                getRowId={(r) => String(r.id)}
              />
            </Card>

            <Card className="p-space-4">
              <h3 className="text-label text-ink-900 font-bold">Quick Actions</h3>
              <p className="text-hint mb-space-3">Common role and permission management tasks.</p>
              <QuickActionList
                columns={2}
                actions={[
                  ...(canWrite
                    ? [{ label: "Add New Role", icon: Plus, onClick: openAddRole }]
                    : [
                        {
                          label: "Add New Role",
                          icon: Plus,
                          disabled: true,
                          title: "You don't have write access to this page.",
                        },
                      ]),
                  { label: "Audit Logs", icon: ScrollText, href: "/portal/settings/activity" },
                ]}
              />
            </Card>
          </div>

          <div className="space-y-space-4">
            <Card className="p-space-4 overflow-x-auto">
              <h3 className="text-label text-ink-900 font-bold">Module Access Overview</h3>
              <p className="text-hint mb-space-3">
                Whether each role can view a module (its own real view permission).
              </p>
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-line text-ink-400 border-b text-left">
                    <th className="py-space-2 pr-space-2 font-semibold">Module</th>
                    {roles.map((role) => (
                      <th key={role.id} className="px-space-1 py-space-2 text-center font-semibold">
                        {role.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PAGE_KEYS.map((pageKey) => (
                    <tr key={pageKey} className="border-line border-b last:border-0">
                      <td className="py-space-2 pr-space-2 text-ink-900">{PAGE_LABEL[pageKey]}</td>
                      {roles.map((role) => {
                        const hasAccess = matrix[role.id]?.[pageKey]?.view;
                        return (
                          <td key={role.id} className="px-space-1 py-space-2 text-center">
                            {hasAccess ? (
                              <Check size={14} className="text-success mx-auto" />
                            ) : (
                              <Minus size={14} className="text-ink-300 mx-auto" />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
        </div>
      )}

      <Dialog open={editingRole !== null} onOpenChange={(open) => !open && setEditingRoleId(null)}>
        <DialogContent className={cn("max-w-2xl")}>
          {editingRole && (
            <>
              <DialogTitle>{editingRole.name} permissions</DialogTitle>
              <p className="text-hint mb-space-3">
                {editingRole.description || "No description set."}
                {!canWrite && " You have view-only access to this page."}
              </p>
              {matrix && (
                <DataTable
                  columns={createRoleColumns({
                    pageLabel: PAGE_LABEL,
                    cellFor: (pageKey) =>
                      matrix[editingRole.id]?.[pageKey] || {
                        view: false,
                        write: false,
                        delete: false,
                      },
                    canWrite,
                    isSaving: (pageKey, action) =>
                      savingCell === `${editingRole.id}:${pageKey}:${action}`,
                    onToggle: (pageKey, action, next) =>
                      handleToggle(editingRole.id, pageKey, action, next),
                  })}
                  data={PAGE_KEYS}
                  getRowId={(pageKey) => pageKey}
                />
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={manageUsersRole !== null}
        onOpenChange={(open) => !open && setManageUsersRoleId(null)}
      >
        <DialogContent className={cn("max-w-2xl")}>
          {manageUsersRole && (
            <>
              <DialogTitle>Users on &quot;{manageUsersRole.name}&quot;</DialogTitle>
              <p className="text-hint mb-space-3">
                Grant or revoke one permission for one specific person -- it always overrides
                whatever this role itself grants them.
              </p>
              {loadingRoleUsers ? (
                <p className="text-ink-400 text-[12.5px]">Loading…</p>
              ) : !roleUsers || roleUsers.length === 0 ? (
                <p className="text-ink-400 text-[12.5px]">No staff members are on this role yet.</p>
              ) : (
                <table className="w-full text-[12.5px]">
                  <thead>
                    <tr className="border-line text-ink-400 border-b text-left">
                      <th className="py-space-2 pr-space-2 font-semibold">Name</th>
                      <th className="py-space-2 pr-space-2 font-semibold">Email</th>
                      <th className="py-space-2 pr-space-2 font-semibold">Status</th>
                      <th className="py-space-2 pr-space-2 font-semibold">Overrides</th>
                      <th className="py-space-2 font-semibold" />
                    </tr>
                  </thead>
                  <tbody>
                    {roleUsers.map((u) => (
                      <tr key={u.staff_id} className="border-line border-b last:border-0">
                        <td className="py-space-2 pr-space-2 text-ink-900">{u.name}</td>
                        <td className="py-space-2 pr-space-2 text-ink-600">{u.email}</td>
                        <td className="py-space-2 pr-space-2">
                          <Badge tone={u.is_active ? "success" : "neutral"}>
                            {u.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </td>
                        <td className="py-space-2 pr-space-2 text-ink-600">
                          {u.overrides.length === 0 ? "—" : `${u.overrides.length} page(s)`}
                        </td>
                        <td className="py-space-2 text-right">
                          <button
                            type="button"
                            onClick={() => setOverrideStaffId(u.staff_id)}
                            disabled={!canWrite}
                            className="border-brand-200 px-space-3 text-brand-700 hover:bg-brand-50 rounded-md border py-1 text-[12px] font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            Permissions
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={overrideStaffId !== null}
        onOpenChange={(open) => !open && setOverrideStaffId(null)}
      >
        <DialogContent className={cn("max-w-2xl")}>
          {manageUsersRole &&
            overrideStaffId !== null &&
            (() => {
              const staffUser = roleUsers?.find((u) => u.staff_id === overrideStaffId);
              if (!staffUser) return null;
              return (
                <>
                  <DialogTitle>{staffUser.name}&apos;s permissions</DialogTitle>
                  <p className="text-hint mb-space-3">
                    On the &quot;{manageUsersRole.name}&quot; role. Each box starts pre-filled with
                    what that role already grants -- check or uncheck one to override it just for{" "}
                    {staffUser.name}; a &quot;Custom&quot; tag appears next to it, click that to
                    reset it back to the role&apos;s own setting.
                  </p>
                  <DataTable
                    columns={createStaffOverrideColumns({
                      pageLabel: PAGE_LABEL,
                      roleDefaultFor: (pageKey) =>
                        matrix?.[manageUsersRole.id]?.[pageKey] || {
                          view: false,
                          write: false,
                          delete: false,
                        },
                      cellFor: (pageKey) => {
                        const o = staffUser.overrides.find((ov) => ov.page_key === pageKey);
                        return o ? { view: o.view, write: o.write, delete: o.delete } : EMPTY_CELL;
                      },
                      canWrite,
                      isSaving: (pageKey) =>
                        savingOverrideCell === `${staffUser.staff_id}:${pageKey}`,
                      onChange: (pageKey, next) =>
                        handleOverrideChange(staffUser.staff_id, pageKey, next),
                    })}
                    data={PAGE_KEYS}
                    getRowId={(pageKey) => pageKey}
                  />
                </>
              );
            })()}
        </DialogContent>
      </Dialog>

      <Dialog open={roleFormOpen} onOpenChange={setRoleFormOpen}>
        <DialogContent>
          <DialogTitle>{renameTarget ? `Rename "${renameTarget.name}"` : "Add role"}</DialogTitle>
          <form onSubmit={handleRoleFormSubmit} className="gap-space-3 flex flex-col">
            <Field label="Name" htmlFor="role_name" required>
              <Input
                id="role_name"
                value={roleForm.name}
                onChange={(e) => setRoleForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </Field>
            <Field label="Description" htmlFor="role_description">
              <Input
                id="role_description"
                value={roleForm.description}
                onChange={(e) => setRoleForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Optional"
              />
            </Field>
            {!renameTarget && (
              <Field
                label="Clone permissions from"
                htmlFor="role_clone"
                hint="Optional -- starts with no access if left blank."
              >
                <select
                  id="role_clone"
                  value={roleForm.cloneFromRoleId}
                  onChange={(e) => setRoleForm((f) => ({ ...f, cloneFromRoleId: e.target.value }))}
                  className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]"
                >
                  <option value="">None (start with no access)</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {roleFormError && (
              <p className="text-error text-[12.5px] font-medium">{roleFormError}</p>
            )}
            <div className="gap-space-2 flex">
              <Button type="submit" size="md" disabled={savingRoleForm}>
                {savingRoleForm ? "Saving…" : renameTarget ? "Save" : "Create role"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={() => setRoleFormOpen(false)}
                disabled={savingRoleForm}
              >
                Cancel
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </PortalShell>
  );
}
