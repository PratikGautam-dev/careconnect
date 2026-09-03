"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { PortalShell } from "@/components/portal/PortalShell";
import { staffFetch, usePermission, useStaffSession, type StaffRole } from "@/lib/staffAuth";

type Action = "view" | "write" | "delete";
type PagePerms = Record<Action, boolean>;
type Matrix = Record<StaffRole, Record<string, PagePerms>>;

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
const ACTIONS: Action[] = ["view", "write", "delete"];

export default function RolesPermissionsPage() {
  const router = useRouter();
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

  const [matrix, setMatrix] = useState<Matrix | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Tracks the single cell currently in flight, e.g. "admin:staff:write", so
  // only that checkbox shows a pending state while its PUT resolves.
  const [savingCell, setSavingCell] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/roles/permissions");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setMatrix((result.data as { permissions: Matrix }).permissions);
  }, [router]);

  useEffect(() => {
    if (canView) load();
  }, [canView, load]);

  async function handleToggle(role: StaffRole, pageKey: string, action: Action, next: boolean) {
    if (!matrix) return;
    const cellKey = `${role}:${pageKey}:${action}`;
    const prevCell = matrix[role][pageKey];
    const nextCell = { ...prevCell, [action]: next };
    setMatrix({ ...matrix, [role]: { ...matrix[role], [pageKey]: nextCell } });
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
        updates: [{
          role,
          page_key: pageKey,
          can_view: nextCell.view,
          can_write: nextCell.write,
          can_delete: nextCell.delete,
        }],
      }),
    });
    setSavingCell(null);
    if (!result.ok) {
      // Roll back on failure -- optimistic update kept the UI responsive
      // (this can be a lot of clicking through a 8x9 grid) but must not
      // silently drift from what the backend actually has stored.
      setMatrix({ ...matrix, [role]: { ...matrix[role], [pageKey]: prevCell } });
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
    }
  }

  if (!canView) {
    return (
      <PortalShell hospital={session?.hospital || null} active="roles">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Roles &amp; Permissions.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={session?.hospital || null} active="roles">
      <h1 className="text-display mb-space-2">Roles &amp; Permissions</h1>
      <p className="text-body mb-space-5">
        Configure what each role can view, edit, and delete across the portal.
        {!canWrite && " You have view-only access to this page."}
      </p>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!matrix ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <div className="space-y-space-5">
          {ROLES.map((role) => (
            <Card key={role} className="overflow-x-auto p-space-4">
              <h3 className="text-label mb-space-3 font-bold text-ink-900">{ROLE_LABEL[role]}</h3>
              <table className="w-full min-w-[480px] border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-line text-left text-ink-600">
                    <th className="py-space-2 pr-space-3 font-semibold">Page</th>
                    {ACTIONS.map((action) => (
                      <th key={action} className="py-space-2 pr-space-3 text-center font-semibold capitalize">
                        {action}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PAGE_KEYS.map((pageKey) => {
                    const cell = matrix[role]?.[pageKey] || { view: false, write: false, delete: false };
                    return (
                      <tr key={pageKey} className="border-b border-line last:border-0">
                        <td className="py-space-2 pr-space-3 text-ink-900">{PAGE_LABEL[pageKey] || pageKey}</td>
                        {ACTIONS.map((action) => {
                          const cellKey = `${role}:${pageKey}:${action}`;
                          return (
                            <td key={action} className="py-space-2 pr-space-3 text-center">
                              <input
                                type="checkbox"
                                checked={cell[action]}
                                disabled={!canWrite || savingCell === cellKey}
                                onChange={(e) => handleToggle(role, pageKey, action, e.target.checked)}
                                className="h-4 w-4 accent-brand-600 disabled:opacity-50"
                              />
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}
    </PortalShell>
  );
}
