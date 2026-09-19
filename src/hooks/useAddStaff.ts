import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { useDepartments } from "@/hooks/useDepartments";
import type { Role } from "@/hooks/usePortalRoles";
import type { WorkingScheduleValue } from "@/components/portal/WorkingScheduleFields";

export type Doctor = { id: string; name: string };
export type StaffOption = { id: number; name: string };

const EMPTY_SCHEDULE: WorkingScheduleValue = {
  working_days: [],
  shifts: [{ start: "", end: "" }],
  breaks: [],
};

/** Owns the "Add staff member" dialog's own form state + submit -- fully
 * self-contained (loads the linked-doctor/department/reports-to/role
 * pickers itself, resets every field the moment it closes) so the dialog
 * can be dropped in anywhere, same open-driven-fetch/reset shape as
 * useNewBooking.ts.
 *
 * presetDoctor (Doctors page's own "Create login" quick action): when set,
 * doctorId is locked to this specific doctor on open -- the admin lands
 * straight on "create THIS doctor's login" rather than re-picking a doctor
 * they already chose by clicking that specific doctor's action. Dynamic-
 * roles migration: doctor-ness is no longer a role property at all (any
 * role can optionally have a doctor linked), so roleId always just
 * defaults to the first fetched role -- the picker itself is immediately
 * visible/editable regardless, and doctorId is a fully independent field. */
export function useAddStaff(
  open: boolean,
  onOpenChange: (open: boolean) => void,
  onCreated?: () => void,
  presetDoctor?: Doctor | null,
) {
  const router = useRouter();
  const departments = useDepartments(open);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [staffOptions, setStaffOptions] = useState<StaffOption[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
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
  const [saving, setSaving] = useState(false);

  const loadDoctors = useCallback(async () => {
    // Reuses the same doctor-list endpoint the Doctors page already fetches
    // from, so a "doctor" staff row can be linked to an existing doctor
    // record instead of duplicating name/specialization entry here.
    const result = await staffFetch("/api/portal/doctors");
    if (!result.ok) return;
    const data = result.data as { doctors: Doctor[] };
    setDoctors(data.doctors || []);
  }, []);

  const loadStaffOptions = useCallback(async () => {
    // For the "Reports to" picker -- GET /api/portal/staff/options, not the
    // Staff page's own GET /api/portal/staff (that one excludes doctors
    // from its directory; this picker still needs to offer a doctor as a
    // valid manager).
    const result = await staffFetch("/api/portal/staff/options");
    if (!result.ok) return;
    setStaffOptions((result.data as StaffOption[]) || []);
  }, []);

  const loadRoles = useCallback(async (): Promise<Role[]> => {
    const result = await staffFetch("/api/portal/roles");
    if (!result.ok) return [];
    const fetched = (result.data as { roles: Role[] }).roles;
    setRoles(fetched);
    return fetched;
  }, []);

  useEffect(() => {
    if (open) {
      loadDoctors();
      loadStaffOptions();
      loadRoles().then((fetched) => {
        // presetDoctor (Doctors page's "Create login" action): default to
        // whichever role is actually named "Doctor" if this hospital still
        // has one -- a convenience default only (the picker stays visible
        // and editable, dynamic-roles migration removed any structural
        // requirement that a doctor's login sit on a particular role), so
        // this never silently lands a new doctor's login on the FIRST role
        // in the list (which sorts Admin first, is_protected DESC).
        const defaultRole = presetDoctor
          ? fetched.find((r) => r.name.toLowerCase() === "doctor") || fetched[0]
          : fetched[0];
        setRoleId(defaultRole?.id ?? null);
      });
      if (presetDoctor) {
        setDoctorId(presetDoctor.id);
        setName(presetDoctor.name);
      }
      return;
    }
    // Closed -- drop everything so the next open starts fresh.
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
  }, [open, loadDoctors, loadStaffOptions, loadRoles, presetDoctor]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!roleId) {
      setFormError("Choose a role.");
      return;
    }
    setSaving(true);
    setFormError(null);
    const working_hours = schedule.shifts
      .filter((s) => s.start && s.end)
      .map((s) => `${s.start}-${s.end}`);
    const breaks = schedule.breaks
      .filter((b) => b && b.start && b.end)
      .map((b) => `${b.start}-${b.end}`);
    const result = await staffFetch("/api/portal/staff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        email,
        password,
        role_id: roleId,
        doctor_id: doctorId || undefined,
        phone: phone || undefined,
        address: address || undefined,
        department_id: !doctorId ? departmentId || undefined : undefined,
        working_days: schedule.working_days,
        working_hours,
        breaks,
        reports_to_id: reportsToId ? Number(reportsToId) : undefined,
      }),
    });
    setSaving(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else {
        setFormError(result.error);
        toast.error("Couldn't create staff member", result.error);
      }
      return;
    }
    toast.success("Staff member created");
    onOpenChange(false);
    onCreated?.();
  }

  return {
    doctors,
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
    setDoctorId,
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
    saving,
    handleCreate,
  };
}
