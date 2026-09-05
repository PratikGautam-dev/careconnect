"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Switch } from "@/components/ui/Switch";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePermission, useStaffSession, type StaffRole } from "@/lib/staffAuth";
import { useStaffManagement } from "@/hooks/useStaffManagement";

const ROLE_LABEL: Record<StaffRole, string> = {
  admin: "Admin",
  receptionist: "Receptionist",
  doctor: "Doctor",
};

export default function StaffManagementPage() {
  // useStaffSession (not getStaffSession directly) -- avoids a hydration
  // mismatch, same reasoning as the roles page's own fix.
  const session = useStaffSession();
  const canView = usePermission("staff", "view");

  const {
    staff, doctors, error, togglingId,
    showForm, toggleForm,
    name, setName, email, setEmail, password, setPassword, role, setRole, doctorId, setDoctorId,
    formError, saving,
    handleCreate, handleToggleActive,
  } = useStaffManagement(canView);

  if (!canView) {
    return (
      <PortalShell hospital={session?.hospital || null} active="staff">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Staff Management.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={session?.hospital || null} active="staff">
      <PageHeader
        title="Staff"
        actions={
          <PermissionGate page="staff" action="write">
            <Button size="md" onClick={toggleForm}>
              {showForm ? "Cancel" : "Add staff member"}
            </Button>
          </PermissionGate>
        }
      />

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <PermissionGate page="staff" action="write">
        {showForm && (
          <Card className="mb-space-4 p-space-4">
            <form onSubmit={handleCreate} className="grid grid-cols-1 gap-space-3 md:grid-cols-2">
              <Field label="Name" htmlFor="staff_name">
                <Input id="staff_name" value={name} onChange={(e) => setName(e.target.value)} required />
              </Field>
              <Field label="Email" htmlFor="staff_email">
                <Input
                  id="staff_email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </Field>
              <Field label="Password" htmlFor="staff_password">
                <Input
                  id="staff_password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </Field>
              <Field label="Role" htmlFor="staff_role">
                <select
                  id="staff_role"
                  value={role}
                  onChange={(e) => setRole(e.target.value as StaffRole)}
                  className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
                >
                  <option value="admin">Admin</option>
                  <option value="receptionist">Receptionist</option>
                  <option value="doctor">Doctor</option>
                </select>
              </Field>
              {role === "doctor" && (
                <Field label="Doctor" htmlFor="staff_doctor" className="md:col-span-2">
                  <select
                    id="staff_doctor"
                    value={doctorId}
                    onChange={(e) => setDoctorId(e.target.value)}
                    className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
                  >
                    <option value="">Select a doctor…</option>
                    {doctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              {formError && <p className="md:col-span-2 text-[12.5px] font-medium text-error">{formError}</p>}
              <div className="md:col-span-2">
                <Button type="submit" disabled={saving || !name || !email || !password} size="md">
                  {saving ? "Creating…" : "Create staff member"}
                </Button>
              </div>
            </form>
          </Card>
        )}
      </PermissionGate>

      <Card className="p-space-4">
        {!staff ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : staff.length === 0 ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">No staff members yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {staff.map((member) => (
              <li key={member.id} className="flex flex-col gap-space-2 py-space-3 sm:flex-row sm:items-center sm:justify-between sm:gap-space-3">
                <div>
                  <p className="text-[13.5px] font-semibold text-ink-900">{member.name}</p>
                  <p className="text-[12px] text-ink-600">{member.email}</p>
                </div>
                <div className="flex items-center gap-space-3">
                  <Badge tone="brand">{ROLE_LABEL[member.role]}</Badge>
                  <Badge tone={member.is_active ? "success" : "neutral"}>
                    {member.is_active ? "Active" : "Deactivated"}
                  </Badge>
                  <PermissionGate page="staff" action="write">
                    <Switch
                      checked={member.is_active}
                      onChange={() => handleToggleActive(member)}
                      disabled={togglingId === member.id}
                      aria-label={`Toggle ${member.name}`}
                    />
                  </PermissionGate>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </PortalShell>
  );
}
