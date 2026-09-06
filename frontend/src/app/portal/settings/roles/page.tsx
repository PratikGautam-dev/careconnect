"use client";

import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePermission, useStaffSession, type StaffRole } from "@/lib/staffAuth";
import { usePortalRoles } from "@/hooks/usePortalRoles";
import { createRoleColumns } from "./_components/role-columns";

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
const ROLES: StaffRole[] = ["admin", "receptionist", "doctor"];
const ROLE_LABEL: Record<StaffRole, string> = { admin: "Admin", receptionist: "Receptionist", doctor: "Doctor" };

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

  const { matrix, error, savingCell, handleToggle } = usePortalRoles(canView);

  if (!canView) {
    return (
      <PortalShell hospital={session?.hospital || null} active="roles">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Roles &amp; Permissions.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={session?.hospital || null} active="roles">
      <PageHeader
        title="Roles & Permissions"
        description={
          <>
            Configure what each role can view, edit, and delete across the portal.
            {!canWrite && " You have view-only access to this page."}
          </>
        }
      />

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!matrix ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <div className="space-y-space-5">
          {ROLES.map((role) => {
            const columns = createRoleColumns({
              pageLabel: PAGE_LABEL,
              cellFor: (pageKey) => matrix[role]?.[pageKey] || { view: false, write: false, delete: false },
              canWrite,
              isSaving: (pageKey, action) => savingCell === `${role}:${pageKey}:${action}`,
              onToggle: (pageKey, action, next) => handleToggle(role, pageKey, action, next),
            });
            return (
              <Card key={role} className="p-space-4">
                <h3 className="text-label mb-space-3 font-bold text-ink-900">{ROLE_LABEL[role]}</h3>
                <DataTable columns={columns} data={PAGE_KEYS} getRowId={(pageKey) => pageKey} />
              </Card>
            );
          })}
        </div>
      )}
    </PortalShell>
  );
}
