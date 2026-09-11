import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch, type StaffRole } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { useDepartments } from "@/hooks/useDepartments";
import type { Shift } from "@/hooks/useStaffManagement";

export type Doctor = { id: string; name: string };
export type StaffOption = { id: number; name: string };

/** Owns the "Add staff member" dialog's own form state + submit -- fully
 * self-contained (loads the linked-doctor/department/reports-to pickers
 * itself, resets every field the moment it closes) so the dialog can be
 * dropped in anywhere, same open-driven-fetch/reset shape as
 * useNewBooking.ts.
 *
 * presetDoctor (Doctors page's own "Create login" quick action): when set,
 * role/doctorId are locked to "doctor"/this doctor on open instead of
 * defaulting to receptionist+unselected -- the admin lands straight on
 * "create THIS doctor's login" rather than re-picking a role and doctor
 * they already chose by clicking that specific doctor's action. */
export function useAddStaff(
  open: boolean, onOpenChange: (open: boolean) => void, onCreated?: () => void, presetDoctor?: Doctor | null,
) {
  const router = useRouter();
  const departments = useDepartments(open);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [staffOptions, setStaffOptions] = useState<StaffOption[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<StaffRole>(presetDoctor ? "doctor" : "receptionist");
  const [doctorId, setDoctorId] = useState(presetDoctor?.id || "");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [shift, setShift] = useState<Shift | "">("");
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
    // For the "Reports to" picker -- reuses the same list the Staff page's
    // own table renders, so a brand-new hire can be assigned a manager who
    // already exists.
    const result = await staffFetch("/api/portal/staff");
    if (!result.ok) return;
    setStaffOptions((result.data as StaffOption[]) || []);
  }, []);

  useEffect(() => {
    if (open) {
      loadDoctors();
      loadStaffOptions();
      if (presetDoctor) {
        setRole("doctor");
        setDoctorId(presetDoctor.id);
        setName(presetDoctor.name);
      }
      return;
    }
    // Closed -- drop everything so the next open starts fresh.
    setName("");
    setEmail("");
    setPassword("");
    setRole(presetDoctor ? "doctor" : "receptionist");
    setDoctorId(presetDoctor?.id || "");
    setPhone("");
    setAddress("");
    setDepartmentId("");
    setShift("");
    setReportsToId("");
    setFormError(null);
  }, [open, loadDoctors, loadStaffOptions, presetDoctor]);

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
        name, email, password, role,
        doctor_id: role === "doctor" ? doctorId : undefined,
        phone: phone || undefined,
        address: address || undefined,
        department_id: role !== "doctor" ? departmentId || undefined : undefined,
        shift: shift || undefined,
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
    doctors, departments, staffOptions,
    name, setName, email, setEmail, password, setPassword, role, setRole, doctorId, setDoctorId,
    phone, setPhone, address, setAddress, departmentId, setDepartmentId, shift, setShift,
    reportsToId, setReportsToId,
    formError, saving, handleCreate,
  };
}
