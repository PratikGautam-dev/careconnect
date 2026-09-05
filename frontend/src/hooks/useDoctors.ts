import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DoctorScheduleFormState, emptyDoctorScheduleForm } from "@/components/portal/DoctorScheduleForm";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Department = { id: string; name: string };
export type Doctor = {
  id: string;
  department_id: string;
  department_name: string;
  name: string;
  specialization: string | null;
  is_active: boolean;
};

/** Loads + owns every mutation on the /portal/doctors page: department
 * creation, doctor add/edit (shared DoctorScheduleForm), active toggle, plus
 * the name/specialization search and active/inactive filter. */
export function useDoctors(ready: boolean) {
  const router = useRouter();
  const [departments, setDepartments] = useState<Department[] | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newDeptName, setNewDeptName] = useState("");
  const [addingDept, setAddingDept] = useState(false);

  const [showDoctorForm, setShowDoctorForm] = useState(false);
  const [showCsvImport, setShowCsvImport] = useState(false);
  const [doctorForm, setDoctorForm] = useState<DoctorScheduleFormState>(emptyDoctorScheduleForm());
  const [doctorErrors, setDoctorErrors] = useState<string[]>([]);
  const [savingDoctor, setSavingDoctor] = useState(false);
  // Doctor-editing follow-up (Spec.md Section 0) -- previously add-only;
  // editing an EXISTING doctor's working hours/breaks/quotas was a known,
  // explicitly flagged gap. Reuses the exact same DoctorScheduleForm the
  // "Add doctor" flow already uses -- editingDoctorId non-null is what
  // distinguishes "save" meaning POST /api/portal/doctors (create) vs
  // POST /api/portal/doctors/{id} (update).
  const [editingDoctorId, setEditingDoctorId] = useState<string | null>(null);
  const [loadingDoctorForEdit, setLoadingDoctorForEdit] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Item 2 (Spec.md Section 0): search (name/specialization) + active/
  // inactive filter, computed client-side (a hospital's own doctor list is
  // small -- no need for a server round trip per keystroke).
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/doctors");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { departments: Department[]; doctors: Doctor[] };
    setDepartments(data.departments);
    setDoctors(data.doctors);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleAddDepartment(e: React.FormEvent) {
    e.preventDefault();
    if (!newDeptName.trim()) return;
    setAddingDept(true);
    const result = await portalFetch("/api/portal/departments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newDeptName.trim() }),
    });
    setAddingDept(false);
    if (result.ok) {
      setNewDeptName("");
      toast.success("Department added");
      load();
    } else if (result.unauthorized) {
      router.push("/portal/login");
    } else {
      toast.error("Couldn't add department", result.error);
    }
  }

  function openAddDoctorForm() {
    setShowDoctorForm((v) => !v);
    setShowCsvImport(false);
    setDoctorForm(emptyDoctorScheduleForm());
    setDoctorErrors([]);
    setEditingDoctorId(null);
  }

  function toggleCsvImport() {
    setShowCsvImport((v) => !v);
    setShowDoctorForm(false);
  }

  function cancelDoctorForm() {
    setShowDoctorForm(false);
    setEditingDoctorId(null);
  }

  async function handleSaveDoctor() {
    setSavingDoctor(true);
    setDoctorErrors([]);
    const working_hours = doctorForm.shifts
      .filter((s) => s.start && s.end)
      .map((s) => `${s.start}-${s.end}`);
    const breaks = doctorForm.breaks
      .filter((b) => b && b.start && b.end)
      .map((b) => `${b.start}-${b.end}`);
    const url = editingDoctorId ? `/api/portal/doctors/${editingDoctorId}` : "/api/portal/doctors";
    const result = await portalFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        department_id: doctorForm.department_id,
        name: doctorForm.name,
        specialization: doctorForm.specialization,
        qualification: doctorForm.qualification,
        years_experience: doctorForm.years_experience,
        working_days: doctorForm.working_days,
        working_hours,
        slot_duration_minutes: doctorForm.slot_duration_minutes,
        breaks,
        max_bookings_per_slot: doctorForm.max_bookings_per_slot,
        daily_booking_limit: doctorForm.daily_booking_limit,
        online_quota: doctorForm.online_quota,
        walkin_quota: doctorForm.walkin_quota,
        followup_duration_minutes: doctorForm.followup_duration_minutes,
        effective_from: doctorForm.effective_from,
      }),
    });
    setSavingDoctor(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else {
        setDoctorErrors([result.error]);
        toast.error(editingDoctorId ? "Couldn't update doctor" : "Couldn't add doctor", result.error);
      }
      return;
    }
    const data = result.data as { errors?: string[] };
    if (data.errors?.length) {
      setDoctorErrors(data.errors);
      toast.error(editingDoctorId ? "Couldn't update doctor" : "Couldn't add doctor", data.errors[0]);
      return;
    }
    toast.success(editingDoctorId ? "Doctor updated" : "Doctor added");
    setDoctorForm(emptyDoctorScheduleForm());
    setShowDoctorForm(false);
    setEditingDoctorId(null);
    load();
  }

  // Doctor-editing follow-up: fetches the full record (working days/hours/
  // breaks/quotas -- get_all_doctors_for_hospital()'s list-page shape above
  // doesn't carry these) and maps it into the same form shape "Add doctor"
  // uses, splitting each stored "HH:MM-HH:MM" string back into a shift/break
  // row.
  async function handleEditDoctor(doc: Doctor) {
    setLoadingDoctorForEdit(doc.id);
    const result = await portalFetch(`/api/portal/doctors/${doc.id}`);
    setLoadingDoctorForEdit(null);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const full = (result.data as { doctor: Record<string, unknown> }).doctor;
    const toRange = (s: string) => {
      const [start, end] = s.split("-");
      return { start: start || "", end: end || "" };
    };
    const shifts = ((full.working_hours as string[]) || []).map(toRange);
    setDoctorForm({
      department_id: (full.department_id as string) || "",
      name: (full.name as string) || "",
      specialization: (full.specialization as string) || "",
      qualification: (full.qualification as string) || "",
      years_experience: full.years_experience != null ? String(full.years_experience) : "",
      working_days: (full.working_days as string[]) || [],
      shifts: shifts.length > 0 ? shifts : [{ start: "", end: "" }],
      breaks: ((full.breaks as string[]) || []).map(toRange),
      slot_duration_minutes: full.slot_duration_minutes != null ? String(full.slot_duration_minutes) : "",
      max_bookings_per_slot: full.max_bookings_per_slot != null ? String(full.max_bookings_per_slot) : "1",
      daily_booking_limit: full.daily_booking_limit != null ? String(full.daily_booking_limit) : "",
      online_quota: full.online_quota != null ? String(full.online_quota) : "",
      walkin_quota: full.walkin_quota != null ? String(full.walkin_quota) : "",
      followup_duration_minutes: full.followup_duration_minutes != null ? String(full.followup_duration_minutes) : "",
      effective_from: (full.effective_from as string) || "",
    });
    setEditingDoctorId(doc.id);
    setDoctorErrors([]);
    setShowCsvImport(false);
    setShowDoctorForm(true);
  }

  async function handleToggleActive(doc: Doctor) {
    setTogglingId(doc.id);
    const result = await portalFetch(`/api/portal/doctors/${doc.id}/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !doc.is_active }),
    });
    setTogglingId(null);
    if (result.ok) {
      toast.success(`Dr. ${doc.name} marked ${doc.is_active ? "unavailable" : "available"}`);
      load();
    } else if (result.unauthorized) {
      router.push("/portal/login");
    } else {
      toast.error("Couldn't update availability", result.error);
    }
  }

  const filteredDoctors = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return doctors.filter((d) => {
      if (activeFilter === "active" && !d.is_active) return false;
      if (activeFilter === "inactive" && d.is_active) return false;
      if (!q) return true;
      return d.name.toLowerCase().includes(q) || (d.specialization || "").toLowerCase().includes(q);
    });
  }, [doctors, searchQuery, activeFilter]);

  return {
    departments, doctors, error, load,
    newDeptName, setNewDeptName, addingDept, handleAddDepartment,
    showDoctorForm, showCsvImport, doctorForm, setDoctorForm, doctorErrors, savingDoctor,
    editingDoctorId, loadingDoctorForEdit,
    openAddDoctorForm, toggleCsvImport, cancelDoctorForm, handleSaveDoctor, handleEditDoctor, handleToggleActive,
    expandedId, setExpandedId, togglingId,
    searchQuery, setSearchQuery, activeFilter, setActiveFilter, filteredDoctors,
  };
}
