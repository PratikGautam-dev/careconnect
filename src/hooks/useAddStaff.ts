import { useState } from "react";
import { useDepartments } from "@/hooks/useDepartments";
import { isPortalMutationError } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import {
  useCreateStaffMember,
  useStaffOptions,
  useStaffRoleOptions,
  type CreateStaffPayload,
} from "@/hooks/useStaff";
import type { WorkingScheduleValue } from "@/components/portal/WorkingScheduleFields";
import { addStaffSchema } from "@/lib/validation/addStaff";

export type AddStaffFieldErrors = { name?: string; email?: string; password?: string };

export type Doctor = { id: string; name: string };

const EMPTY_SCHEDULE: WorkingScheduleValue = {
  working_days: [],
  shifts: [{ start: "", end: "" }],
  breaks: [],
};

/** Owns the "Add staff member" dialog's own form state + submit -- fully
 * self-contained (loads the department/reports-to/role pickers itself,
 * resets every field the moment it closes) so the dialog can be dropped in
 * anywhere, same open-driven-fetch/reset shape as useNewBooking.ts.
 *
 * presetDoctor (Doctors page's own "Create login" quick action): when set,
 * doctorId is locked to this specific doctor on open -- the admin lands
 * straight on "create THIS doctor's login" rather than re-picking a doctor
 * they already chose by clicking that specific doctor's action. This is
 * the ONLY way doctorId ever gets set now -- the generic "Add staff
 * member" flow (no presetDoctor) used to also offer a "Link to existing
 * doctor" picker here, removed (confirmed with the user) as a redundant,
 * less-guided duplicate of this same preset flow: doctor creation itself
 * never asks for login details, so the Doctors page's own "Create login"
 * action is already the one, correctly-guided way to grant an existing
 * doctor a login (it also locks the role to "Doctor", which the removed
 * generic picker never enforced). Dynamic-roles migration: doctor-ness is
 * no longer a role property at all (any role can optionally have a doctor
 * linked), so roleId always just defaults to the first fetched role -- the
 * picker itself is immediately visible/editable regardless, and doctorId
 * is a fully independent field. */
export function useAddStaff(
  open: boolean,
  onOpenChange: (open: boolean) => void,
  onCreated?: () => void,
  presetDoctor?: Doctor | null,
) {
  const departments = useDepartments(open);
  const { staffOptions } = useStaffOptions(open);
  const { roles } = useStaffRoleOptions(open);
  const createStaffMember = useCreateStaffMember();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleId, setRoleId] = useState<number | null>(null);
  const [doctorId, setDoctorId] = useState(presetDoctor?.id || "");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [schedule, setSchedule] = useState<WorkingScheduleValue>(EMPTY_SCHEDULE);
  const [reportsToId, setReportsToId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<AddStaffFieldErrors>({});

  const [seededOpen, setSeededOpen] = useState(false);
  const [roleDefaulted, setRoleDefaulted] = useState(false);

  // roles arrives asynchronously (its own query, keyed off `open`) -- this
  // picks a default the moment a role list actually becomes available,
  // computed during render (not an effect) so it doesn't cost an extra
  // render cycle each time. `roleDefaulted` guards it to exactly once per
  // open, so a later manual pick in the dropdown is never clobbered once
  // the (possibly slower) roles fetch resolves.
  if (open && !roleDefaulted && roles.length > 0) {
    setRoleDefaulted(true);
    const defaultRole = presetDoctor
      ? roles.find((r) => r.name.toLowerCase() === "doctor") || roles[0]
      : roles[0];
    setRoleId(defaultRole?.id ?? null);
  }

  if (open && !seededOpen) {
    setSeededOpen(true);
    if (presetDoctor) {
      setDoctorId(presetDoctor.id);
      setName(presetDoctor.name);
    }
  } else if (!open && seededOpen) {
    setSeededOpen(false);
    setRoleDefaulted(false);
    setName("");
    setEmail("");
    setPassword("");
    setRoleId(null);
    setDoctorId(presetDoctor?.id || "");
    setPhone("");
    setAddress("");
    setDepartmentId("");
    setSchedule(EMPTY_SCHEDULE);
    setReportsToId("");
    setFormError(null);
    setFieldErrors({});
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    // Mirrors portal/routes/staff.py's own required checks (name/email/
    // password >= 8 chars) client-side, before the round-trip -- same
    // "client mirrors the backend's own rule" reasoning setStaffPassword.ts
    // already uses for password-reset dialogs elsewhere in this app.
    const parsed = addStaffSchema.safeParse({ name, email, password });
    if (!parsed.success) {
      const errors: AddStaffFieldErrors = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] as keyof AddStaffFieldErrors;
        if (!errors[key]) errors[key] = issue.message;
      }
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    if (!roleId) {
      setFormError("Choose a role.");
      return;
    }
    setFormError(null);
    const working_hours = schedule.shifts
      .filter((s) => s.start && s.end)
      .map((s) => `${s.start}-${s.end}`);
    const breaks = schedule.breaks
      .filter((b) => b && b.start && b.end)
      .map((b) => `${b.start}-${b.end}`);
    const payload: CreateStaffPayload = {
      name: parsed.data.name,
      email: parsed.data.email,
      password: parsed.data.password,
      role_id: roleId,
      doctor_id: doctorId || undefined,
      phone: phone || undefined,
      address: address || undefined,
      department_id: !doctorId ? departmentId || undefined : undefined,
      working_days: schedule.working_days,
      working_hours,
      breaks,
      reports_to_id: reportsToId ? Number(reportsToId) : undefined,
    };
    try {
      await createStaffMember.mutateAsync(payload);
      toast.success("Staff member created");
      onOpenChange(false);
      onCreated?.();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setFormError(err.message);
        toast.error("Couldn't create staff member", err.message);
      }
    }
  }

  return {
    departments,
    staffOptions,
    roles,
    name,
    setName,
    email,
    setEmail,
    password,
    setPassword,
    roleId,
    setRoleId,
    doctorId,
    phone,
    setPhone,
    address,
    setAddress,
    departmentId,
    setDepartmentId,
    schedule,
    setSchedule,
    reportsToId,
    setReportsToId,
    formError,
    fieldErrors,
    saving: createStaffMember.isPending,
    handleCreate,
  };
}
