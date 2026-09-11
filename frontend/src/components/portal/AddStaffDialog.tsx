"use client";

import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { StaffContactFields } from "./StaffContactFields";
import { useAddStaff, type Doctor } from "@/hooks/useAddStaff";
import type { StaffRole } from "@/lib/staffAuth";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Fired the moment a staff member is created -- lets the caller's own
   * list refresh; the dialog closes itself on success. */
  onCreated?: () => void;
  /** Doctors page's own "Create login" quick action -- locks role/doctor to
   * this one doctor instead of showing the Role/Doctor pickers, so the form
   * is just "set this doctor's login email + password". */
  presetDoctor?: Doctor | null;
};

const ROLE_OPTIONS: { value: StaffRole; label: string }[] = [
  { value: "admin", label: "Admin" },
  { value: "receptionist", label: "Receptionist" },
  { value: "doctor", label: "Doctor" },
];

/** Reusable "Add staff member" modal -- same self-contained dialog+hook
 * shape as NewBookingDialog/useNewBooking, so it can open from the Staff
 * page's own header button and the dashboard's Quick Actions alike instead
 * of each place hand-rolling its own inline form. */
export function AddStaffDialog({ open, onOpenChange, onCreated, presetDoctor }: Props) {
  const {
    doctors, departments, staffOptions,
    name, setName, email, setEmail, password, setPassword, role, setRole, doctorId, setDoctorId,
    phone, setPhone, address, setAddress, departmentId, setDepartmentId, shift, setShift,
    reportsToId, setReportsToId,
    formError, saving, handleCreate,
  } = useAddStaff(open, onOpenChange, onCreated, presetDoctor);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{presetDoctor ? `Create login for Dr. ${presetDoctor.name}` : "Add staff member"}</DialogTitle>
        <form onSubmit={handleCreate} className="mt-space-3 grid grid-cols-1 gap-space-3 md:grid-cols-2">
          <Field label="Name" htmlFor="staff_name">
            <Input id="staff_name" value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>
          <Field label="Email" htmlFor="staff_email">
            <Input id="staff_email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password" htmlFor="staff_password">
            <Input id="staff_password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {!presetDoctor && (
            <Field label="Role" htmlFor="staff_role">
              <select
                id="staff_role"
                value={role}
                onChange={(e) => setRole(e.target.value as StaffRole)}
                className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {role === "doctor" && !presetDoctor && (
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
          <StaffContactFields
            role={role}
            phone={phone} setPhone={setPhone}
            address={address} setAddress={setAddress}
            departmentId={departmentId} setDepartmentId={setDepartmentId} departments={departments}
            shift={shift} setShift={setShift}
            reportsToId={reportsToId} setReportsToId={setReportsToId} staffOptions={staffOptions}
          />
          {formError && <p className="text-[12.5px] font-medium text-error md:col-span-2">{formError}</p>}
          <div className="md:col-span-2">
            <Button type="submit" disabled={saving || !name || !email || !password} size="md">
              {saving ? "Creating…" : presetDoctor ? "Create login" : "Create staff member"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
