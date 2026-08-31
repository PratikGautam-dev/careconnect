"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { getStaffSession, staffFetch, usePermission, type StaffRole } from "@/lib/staffAuth";

type StaffMember = { id: number; name: string; email: string; role: StaffRole; is_active: boolean };
type Doctor = { id: string; name: string };

const ROLE_LABEL: Record<StaffRole, string> = {
  admin: "Admin",
  receptionist: "Receptionist",
  doctor: "Doctor",
};

export default function StaffManagementPage() {
  const router = useRouter();
  const session = getStaffSession();
  const canView = usePermission("staff", "view");

  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<StaffRole>("receptionist");
  const [doctorId, setDoctorId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/staff");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setStaff(result.data as StaffMember[]);
  }, [router]);

  const loadDoctors = useCallback(async () => {
    // Reuses the same doctor-list endpoint the Doctors page already fetches
    // from, so a "doctor" staff row can be linked to an existing doctor
    // record instead of duplicating name/specialization entry here.
    const result = await staffFetch("/api/portal/doctors");
    if (!result.ok) return;
    const data = result.data as { doctors: Doctor[] };
    setDoctors(data.doctors || []);
  }, []);

  useEffect(() => {
    if (!canView) return;
    load();
    loadDoctors();
  }, [canView, load, loadDoctors]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (role === "doctor" && !doctorId) {
      setFormError("Select which doctor this login belongs to.");
      return;
    }
    setSaving(true);
    setFormError(null);
    const result = await staffFetch("/api/portal/staff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        email,
        password,
        role,
        doctor_id: role === "doctor" ? doctorId : undefined,
      }),
    });
    setSaving(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setFormError(result.error);
      return;
    }
    setName("");
    setEmail("");
    setPassword("");
    setRole("receptionist");
    setDoctorId("");
    setShowForm(false);
    load();
  }

  async function handleToggleActive(member: StaffMember) {
    setTogglingId(member.id);
    const result = await staffFetch(`/api/portal/staff/${member.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !member.is_active }),
    });
    setTogglingId(null);
    if (result.ok) load();
    else if (result.unauthorized) router.push("/portal/login");
  }

  if (!canView) {
    return (
      <PortalShell hospital={session?.hospital || null} active="staff">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Staff Management.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={session?.hospital || null} active="staff">
      <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
        <h1 className="text-display">Staff</h1>
        <PermissionGate page="staff" action="write">
          <Button
            size="md"
            onClick={() => {
              setShowForm((v) => !v);
              setFormError(null);
            }}
          >
            {showForm ? "Cancel" : "Add staff member"}
          </Button>
        </PermissionGate>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <PermissionGate page="staff" action="write">
        {showForm && (
          <Card className="mb-space-4 p-space-4">
            <form onSubmit={handleCreate} className="grid grid-cols-1 gap-space-3 sm:grid-cols-2">
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
                <Field label="Doctor" htmlFor="staff_doctor" className="sm:col-span-2">
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
              {formError && <p className="sm:col-span-2 text-[12.5px] font-medium text-error">{formError}</p>}
              <div className="sm:col-span-2">
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
              <li key={member.id} className="flex items-center justify-between gap-space-3 py-space-3">
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
                    <button
                      type="button"
                      onClick={() => handleToggleActive(member)}
                      disabled={togglingId === member.id}
                      role="switch"
                      aria-checked={member.is_active}
                      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${
                        member.is_active ? "bg-brand-600" : "bg-line"
                      } ${togglingId === member.id ? "opacity-60" : ""}`}
                    >
                      <span
                        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${
                          member.is_active ? "translate-x-[22px]" : "translate-x-0.5"
                        }`}
                      />
                    </button>
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
