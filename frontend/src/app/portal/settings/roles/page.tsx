"use client";

import { useState } from "react";
import {
  Building2,
  Check,
  ClipboardList,
  KeyRound,
  Minus,
  Plus,
  ScrollText,
  ShieldCheck,
  Stethoscope,
  UserRound,
  Users,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { cn } from "@/lib/cn";
import { usePermission, useStaffSession, type StaffRole } from "@/lib/staffAuth";
import { usePortalRoles } from "@/hooks/usePortalRoles";
import { createRoleColumns, createRoleManagementColumns } from "./_components/role-columns";

const PAGE_KEYS = ["dashboard", "appointments", "patients", "schedule", "doctors", "diagnostic_tests", "messages", "settings", "staff", "roles"];
const PAGE_LABEL: Record<string, string> = {
  dashboard: "Dashboard",
  appointments: "Appointments",
  patients: "Patients",
  schedule: "Schedule",
  doctors: "Doctors",
  diagnostic_tests: "Diagnostic Tests",
  messages: "Messages",
  settings: "Settings",
  staff: "Staff",
  roles: "Roles & Permissions",
};

// The reference mockup shows a 7th "Super Admin" role -- omitted here since
// it's a cross-tenant/operator role (admin/*, a different app area
// entirely), not a hospital-portal role at all. Only these 3 are real:
// staff_users.role is a fixed CHECK ('admin', 'receptionist', 'doctor'),
// not a table -- there's no dynamic/custom role concept in this schema
// (confirmed with the user), so this page shows exactly these 3 and no
// "Add Role" capability.
const ROLES: StaffRole[] = ["admin", "receptionist", "doctor"];
const ROLE_LABEL: Record<StaffRole, string> = { admin: "Admin", receptionist: "Receptionist", doctor: "Doctor" };
const ROLE_ICON: Record<StaffRole, typeof Building2> = { admin: Building2, doctor: Stethoscope, receptionist: UserRound };
const ROLE_DESCRIPTION: Record<StaffRole, string> = {
  admin: "Manages hospital operations, staff, doctors, and configurations.",
  doctor: "Access to own patient appointments, schedule, and messages.",
  receptionist: "Manages patient registrations, appointments, and front-desk messages.",
};

export default function RolesPermissionsPage() {
  // useStaffSession (not getStaffSession directly): null on the server AND
  // on the client's own first render, so PortalShell/PortalSidebar render
  // the same "Hospital" placeholder both places -- getStaffSession() itself
  // returns the real session immediately client-side (synchronous
  // localStorage), which used to disagree with the server's render and
  // throw a hydration-mismatch error the instant the real hospital name
  // reached the DOM.
  const session = useStaffSession();
  const canView = usePermission("roles", "view");
  const canWrite = usePermission("roles", "write");

  const { matrix, error, savingCell, handleToggle, staffCounts } = usePortalRoles(canView);
  const [editingRole, setEditingRole] = useState<StaffRole | null>(null);

  if (!canView) {
    return (
      <PortalShell hospital={session?.hospital || null} active="roles">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Roles &amp; Permissions.</p>
      </PortalShell>
    );
  }

  const totalPermissionCells = ROLES.length * PAGE_KEYS.length;
  const activeRoleCount = ROLES.filter((r) => staffCounts.activeByRole[r] > 0).length;

  const roleManagementColumns = createRoleManagementColumns({
    roleLabel: ROLE_LABEL,
    roleDescription: ROLE_DESCRIPTION,
    roleIcon: ROLE_ICON,
    userCountFor: (role) => staffCounts.byRole[role] || 0,
    onEditPermissions: setEditingRole,
  });

  return (
    <PortalShell hospital={session?.hospital || null} active="roles">
      <PageHeader
        title="Roles & Permissions"
        description="Manage user roles, permissions and access across the portal."
      />

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <div className="mb-space-4 grid grid-cols-1 gap-space-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Total Roles" value={ROLES.length} deltaPct={null} hint="Built-in roles in this app" icon={Users} />
        <StatTile label="Total Users" value={staffCounts.total} deltaPct={null} hint="Across all roles" icon={UserRound} />
        <StatTile
          label="Active Roles"
          value={activeRoleCount}
          deltaPct={null}
          hint={`of ${ROLES.length} have an active user`}
          icon={ShieldCheck}
          tint="success"
        />
        <StatTile label="Total Permissions" value={totalPermissionCells} deltaPct={null} hint="Role x module combinations" icon={KeyRound} />
      </div>

      {!matrix ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_360px]">
          <div className="space-y-space-4">
            <Card className="p-space-4">
              <div className="mb-space-3">
                <h3 className="text-label font-bold text-ink-900">Role Management</h3>
                <p className="text-hint">
                  {ROLES.length} built-in roles for this portal.{!canWrite && " You have view-only access."}
                </p>
              </div>
              <DataTable columns={roleManagementColumns} data={ROLES} getRowId={(r) => r} />
            </Card>

            <Card className="p-space-4">
              <h3 className="text-label font-bold text-ink-900">Quick Actions</h3>
              <p className="text-hint mb-space-3">Common role and permission management tasks.</p>
              <QuickActionList
                columns={2}
                actions={[
                  {
                    label: "Add New Role",
                    icon: Plus,
                    disabled: true,
                    title: "Roles are fixed in this app — Admin, Receptionist and Doctor only, no custom roles yet.",
                  },
                  { label: "Manage Users", icon: Users, href: "/portal/settings/staff" },
                  {
                    label: "Permission Templates",
                    icon: ClipboardList,
                    disabled: true,
                    title: "Coming soon — bulk permission templates aren't built yet.",
                  },
                  { label: "Audit Logs", icon: ScrollText, href: "/portal/settings/activity" },
                ]}
              />
            </Card>
          </div>

          <div className="space-y-space-4">
            <Card className="overflow-x-auto p-space-4">
              <h3 className="text-label font-bold text-ink-900">Module Access Overview</h3>
              <p className="text-hint mb-space-3">Whether each role can view a module (its own real view permission).</p>
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-line text-left text-ink-400">
                    <th className="py-space-2 pr-space-2 font-semibold">Module</th>
                    {ROLES.map((role) => (
                      <th key={role} className="px-space-1 py-space-2 text-center font-semibold">
                        {ROLE_LABEL[role]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PAGE_KEYS.map((pageKey) => (
                    <tr key={pageKey} className="border-b border-line last:border-0">
                      <td className="py-space-2 pr-space-2 text-ink-900">{PAGE_LABEL[pageKey]}</td>
                      {ROLES.map((role) => {
                        const hasAccess = matrix[role]?.[pageKey]?.view;
                        return (
                          <td key={role} className="px-space-1 py-space-2 text-center">
                            {hasAccess ? (
                              <Check size={14} className="mx-auto text-success" />
                            ) : (
                              <Minus size={14} className="mx-auto text-ink-300" />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <Card className="p-space-4">
              <h3 className="text-label font-bold text-ink-900">Permission Templates</h3>
              <p className="text-hint mb-space-3">Jump straight to a role&apos;s own permission editor.</p>
              <div className="space-y-space-1">
                {ROLES.map((role) => {
                  const Icon = ROLE_ICON[role];
                  return (
                    <button
                      key={role}
                      type="button"
                      onClick={() => setEditingRole(role)}
                      className="flex w-full items-center justify-between rounded-md px-space-2 py-space-2 text-left text-[13px] font-semibold text-ink-900 hover:bg-black/[0.03]"
                    >
                      <span className="flex items-center gap-space-2">
                        <Icon size={15} className="text-brand-600" /> {ROLE_LABEL[role]} Template
                      </span>
                      <span className="text-ink-400">›</span>
                    </button>
                  );
                })}
              </div>
            </Card>
          </div>
        </div>
      )}

      <Dialog open={editingRole !== null} onOpenChange={(open) => !open && setEditingRole(null)}>
        <DialogContent className={cn("max-w-2xl")}>
          {editingRole && (
            <>
              <DialogTitle>{ROLE_LABEL[editingRole]} permissions</DialogTitle>
              <p className="text-hint mb-space-3">
                {ROLE_DESCRIPTION[editingRole]}
                {!canWrite && " You have view-only access to this page."}
              </p>
              {matrix && (
                <DataTable
                  columns={createRoleColumns({
                    pageLabel: PAGE_LABEL,
                    cellFor: (pageKey) => matrix[editingRole]?.[pageKey] || { view: false, write: false, delete: false },
                    canWrite,
                    isSaving: (pageKey, action) => savingCell === `${editingRole}:${pageKey}:${action}`,
                    onToggle: (pageKey, action, next) => handleToggle(editingRole, pageKey, action, next),
                  })}
                  data={PAGE_KEYS}
                  getRowId={(pageKey) => pageKey}
                />
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </PortalShell>
  );
}
