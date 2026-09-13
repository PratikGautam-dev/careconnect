"use client";

import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { SectionHeader } from "./SectionHeader";
import { StaffContactFields } from "./StaffContactFields";
import { useAddStaff, type Doctor } from "@/hooks/useAddStaff";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Fired the moment a staff member is created -- lets the caller's own
   * list refresh; the dialog closes itself on success. */
  onCreated?: () => void;
  /** Doctors page's own "Create login" quick action -- locks role/doctor to
   * this one doctor (both pickers hidden), auto-assigning whichever role is
   * named "Doctor" at this hospital. Falls back to SHOWING the Role picker
   * only if no such role exists (renamed/deleted) -- the admin isn't
   * silently stuck landing on whatever role sorts first (Admin, the one
   * protected role) in that edge case. */
  presetDoctor?: Doctor | null;
};

/** Reusable "Add staff member" modal -- same self-contained dialog+hook
 * shape as NewBookingDialog/useNewBooking, so it can open from the Staff
 * page's own header button and the dashboard's Quick Actions alike instead
 * of each place hand-rolling its own inline form. */
export function AddStaffDialog({ open, onOpenChange, onCreated, presetDoctor }: Props) {
  const {
    doctors, departments, staffOptions, roles,
    name, setName, email, setEmail, password, setPassword, roleId, setRoleId, doctorId, setDoctorId,
    phone, setPhone, address, setAddress, departmentId, setDepartmentId, schedule, setSchedule,
    reportsToId, setReportsToId,
    formError, saving, handleCreate,
  } = useAddStaff(open, onOpenChange, onCreated, presetDoctor);
  const hasNamedDoctorRole = roles.some((r) => r.name.toLowerCase() === "doctor");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{presetDoctor ? `Create login for Dr. ${presetDoctor.name}` : "Add staff member"}</DialogTitle>
        <form onSubmit={handleCreate} className="mt-space-3 grid grid-cols-1 gap-space-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <SectionHeader
              title="Login details"
              description={
                presetDoctor
                  ? "The email and password this doctor will use to sign into the portal."
                  : "Who this staff member is and the email/password they'll sign in with."
              }
            />
          </div>
          <Field label="Name" htmlFor="staff_name">
            <Input id="staff_name" value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>
          <Field label="Email" htmlFor="staff_email">
            <Input id="staff_email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password" htmlFor="staff_password">
            <Input id="staff_password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {(!presetDoctor || !hasNamedDoctorRole) && (
            <Field
              label="Role" htmlFor="staff_role"
              hint={presetDoctor ? 'No role named "Doctor" was found -- choose one for this login.' : undefined}
            >
              <select
                id="staff_role"
                value={roleId ?? ""}
                onChange={(e) => setRoleId(e.target.value ? Number(e.target.value) : null)}
                className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
              >
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {!presetDoctor && (
            <Field
              label="Link to existing doctor" htmlFor="staff_doctor" className="md:col-span-2"
              hint="Optional -- links this login to a doctor profile (their department then comes from there instead)."
            >
              <select
                id="staff_doctor"
                value={doctorId}
                onChange={(e) => setDoctorId(e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
              >
                <option value="">No doctor linked</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <div className="mt-space-2 border-t border-line pt-space-4 md:col-span-2">
            <SectionHeader
              title="Profile information"
              description="Contact details, department and who they report to -- shown on their staff profile."
            />
          </div>
          <StaffContactFields
            hasLinkedDoctor={!!doctorId}
            phone={phone} setPhone={setPhone}
            address={address} setAddress={setAddress}
            departmentId={departmentId} setDepartmentId={setDepartmentId} departments={departments}
            schedule={schedule} setSchedule={setSchedule}
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
