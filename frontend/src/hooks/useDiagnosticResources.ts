import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Department = { id: string; name: string };
export type Resource = { id: string; name: string; department_id: string | null; is_active: boolean };
export type ResourceFull = Resource & {
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  slot_duration_minutes: number;
  max_bookings_per_slot: number;
  daily_booking_limit: number | null;
  effective_from: string | null;
};

export type FormState = {
  name: string;
  department_id: string;
  working_days: string[];
  shift_start: string;
  shift_end: string;
  break_start: string;
  break_end: string;
  slot_duration_minutes: string;
  max_bookings_per_slot: string;
  daily_booking_limit: string;
  effective_from: string;
};

function emptyForm(): FormState {
  return {
    name: "", department_id: "", working_days: [], shift_start: "", shift_end: "",
    break_start: "", break_end: "", slot_duration_minutes: "30", max_bookings_per_slot: "1",
    daily_booking_limit: "", effective_from: "",
  };
}

function formFromResource(r: ResourceFull): FormState {
  const [shift_start = "", shift_end = ""] = (r.working_hours[0] || "").split("-");
  const [break_start = "", break_end = ""] = (r.breaks[0] || "").split("-");
  return {
    name: r.name, department_id: r.department_id || "", working_days: r.working_days,
    shift_start, shift_end, break_start, break_end,
    slot_duration_minutes: String(r.slot_duration_minutes), max_bookings_per_slot: String(r.max_bookings_per_slot),
    daily_booking_limit: r.daily_booking_limit != null ? String(r.daily_booking_limit) : "",
    effective_from: r.effective_from || "",
  };
}

/** Loads + owns every mutation on the Diagnostic/Lab resource list (bookable
 * machines/equipment): add/edit form state, active toggle, plus the
 * department list the form's picker needs. */
export function useDiagnosticResources() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [resources, setResources] = useState<Resource[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [deptResult, resResult] = await Promise.all([
      portalFetch("/api/portal/doctors"),
      portalFetch("/api/portal/diagnostic-resources"),
    ]);
    if (deptResult.ok) setDepartments((deptResult.data as { departments: Department[] }).departments);
    if (resResult.ok) setResources((resResult.data as { resources: Resource[] }).resources);
    else if (resResult.unauthorized === false) setResources([]);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function toggleDay(day: string) {
    setForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day) ? f.working_days.filter((d) => d !== day) : [...f.working_days, day],
    }));
  }

  function openAddForm() {
    setEditingId(null);
    setForm(emptyForm());
    setShowForm(true);
  }

  async function openEditForm(r: Resource) {
    const result = await portalFetch(`/api/portal/diagnostic-resources/${r.id}`);
    if (!result.ok) return;
    setEditingId(r.id);
    setForm(formFromResource((result.data as { resource: ResourceFull }).resource));
    setShowForm(true);
  }

  async function handleSave() {
    if (!form.name.trim()) return;
    setSaving(true);
    setError(null);
    const payload = {
      name: form.name.trim(),
      department_id: form.department_id || null,
      working_days: form.working_days,
      working_hours: form.shift_start && form.shift_end ? [`${form.shift_start}-${form.shift_end}`] : [],
      breaks: form.break_start && form.break_end ? [`${form.break_start}-${form.break_end}`] : [],
      slot_duration_minutes: Number(form.slot_duration_minutes) || 30,
      max_bookings_per_slot: Number(form.max_bookings_per_slot) || 1,
      daily_booking_limit: form.daily_booking_limit ? Number(form.daily_booking_limit) : null,
      effective_from: form.effective_from || null,
    };
    const result = editingId
      ? await portalFetch(`/api/portal/diagnostic-resources/${editingId}`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        })
      : await portalFetch("/api/portal/diagnostic-resources", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
    setSaving(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error(editingId ? "Couldn't update resource" : "Couldn't add resource", result.error);
      return;
    }
    toast.success(editingId ? "Resource updated" : "Resource added");
    setShowForm(false);
    load();
  }

  async function handleToggleActive(r: Resource) {
    setTogglingId(r.id);
    const result = await portalFetch(`/api/portal/diagnostic-resources/${r.id}/active`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !r.is_active }),
    });
    setTogglingId(null);
    if (result.ok) {
      toast.success(r.is_active ? "Resource deactivated" : "Resource activated");
      load();
    } else if (!result.unauthorized) {
      toast.error("Couldn't update resource", result.error);
    }
  }

  return {
    departments, resources, error,
    showForm, setShowForm, editingId, form, setForm, saving, togglingId, expandedId, setExpandedId,
    toggleDay, openAddForm, openEditForm, handleSave, handleToggleActive,
  };
}
