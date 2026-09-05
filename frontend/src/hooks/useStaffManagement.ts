import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch, type StaffRole } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

export type StaffMember = { id: number; name: string; email: string; role: StaffRole; is_active: boolean };
export type Doctor = { id: string; name: string };

/** Loads + owns every mutation on /portal/settings/staff: the staff list,
 * the linked-doctor picker, create-staff-member form state, and the
 * active/inactive toggle. */
export function useStaffManagement(canView: boolean) {
  const router = useRouter();

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

  function toggleForm() {
    setShowForm((v) => !v);
    setFormError(null);
  }

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
      else {
        setFormError(result.error);
        toast.error("Couldn't create staff member", result.error);
      }
      return;
    }
    toast.success("Staff member created");
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
    if (result.ok) {
      toast.success(member.is_active ? "Staff member deactivated" : "Staff member activated");
      load();
    } else if (result.unauthorized) {
      router.push("/portal/login");
    } else {
      toast.error("Couldn't update staff member", result.error);
    }
  }

  return {
    staff, doctors, error, togglingId,
    showForm, toggleForm,
    name, setName, email, setEmail, password, setPassword, role, setRole, doctorId, setDoctorId,
    formError, saving,
    handleCreate, handleToggleActive,
  };
}
