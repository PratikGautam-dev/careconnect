"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Pencil, Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";
import { ResourceLeaveManager } from "@/components/portal/ResourceLeaveManager";
import { ResourceSlotManager } from "@/components/portal/ResourceSlotManager";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Department = { id: string; name: string };
type Resource = { id: string; name: string; department_id: string | null; is_active: boolean };
type ResourceFull = Resource & {
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  slot_duration_minutes: number;
  max_bookings_per_slot: number;
  daily_booking_limit: number | null;
  effective_from: string | null;
};

type FormState = {
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

export function DiagnosticResourcesManager({ canManage }: { canManage: boolean }) {
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
      return;
    }
    setShowForm(false);
    load();
  }

  async function handleToggleActive(r: Resource) {
    setTogglingId(r.id);
    const result = await portalFetch(`/api/portal/diagnostic-resources/${r.id}/active`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !r.is_active }),
    });
    setTogglingId(null);
    if (result.ok) load();
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">Resources</h3>
        {canManage && !showForm && (
          <Button size="md" onClick={openAddForm}>
            <Plus size={14} /> Add resource
          </Button>
        )}
      </div>
      <p className="mb-space-3 text-[12px] text-ink-400">
        Bookable machines/equipment (e.g. an MRI machine) with their own weekly schedule -- a Diagnostic Test linked to
        one only offers slots when that resource is actually free.
      </p>
      {error && <p className="mb-space-3 text-[12.5px] text-error">{error}</p>}

      {showForm && (
        <div className="mb-space-4 rounded-lg border border-line bg-paper p-space-4">
          <div className="mb-space-3 flex items-center justify-between">
            <p className="text-label font-semibold text-ink-900">{editingId ? "Edit resource" : "Add resource"}</p>
            <button type="button" onClick={() => setShowForm(false)} className="text-ink-400 hover:text-ink-700">
              <X size={16} />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-x-space-4 md:grid-cols-2">
            <Field label="Name" htmlFor="resource_name" required>
              <Input id="resource_name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Department" htmlFor="resource_department" hint="optional">
              <select
                id="resource_department"
                value={form.department_id}
                onChange={(e) => setForm({ ...form, department_id: e.target.value })}
                className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900"
              >
                <option value="">None</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Working days">
            <div className="flex flex-wrap items-center gap-space-2">
              {WEEKDAYS.map((day) => {
                const on = form.working_days.includes(day);
                return (
                  <button
                    key={day} type="button" onClick={() => toggleDay(day)}
                    className={cn(
                      "flex h-9 w-14 items-center justify-center rounded-md border text-[12.5px] font-semibold transition-colors duration-150",
                      on ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600 hover:border-brand-300",
                    )}
                  >
                    {day}
                  </button>
                );
              })}
            </div>
          </Field>

          <div className="mb-space-3 flex flex-wrap items-center gap-space-2 rounded-lg border border-line bg-card p-space-3">
            <span className="w-14 shrink-0 text-[12.5px] font-semibold text-ink-600">Hours</span>
            <Input type="time" value={form.shift_start} onChange={(e) => setForm({ ...form, shift_start: e.target.value })} className="w-32" />
            <span className="text-[12.5px] text-ink-400">to</span>
            <Input type="time" value={form.shift_end} onChange={(e) => setForm({ ...form, shift_end: e.target.value })} className="w-32" />
            <span className="ml-space-3 w-12 shrink-0 text-[12.5px] font-semibold text-ink-600">Break</span>
            <Input type="time" value={form.break_start} onChange={(e) => setForm({ ...form, break_start: e.target.value })} className="w-32" />
            <span className="text-[12.5px] text-ink-400">to</span>
            <Input type="time" value={form.break_end} onChange={(e) => setForm({ ...form, break_end: e.target.value })} className="w-32" />
          </div>

          <div className="grid grid-cols-1 gap-x-space-4 md:grid-cols-3">
            <Field label="Slot duration" htmlFor="resource_slot_duration" hint="minutes">
              <Input id="resource_slot_duration" type="number" min={1} value={form.slot_duration_minutes} onChange={(e) => setForm({ ...form, slot_duration_minutes: e.target.value })} />
            </Field>
            <Field label="Max bookings" htmlFor="resource_max_bookings" hint="per slot">
              <Input id="resource_max_bookings" type="number" min={1} value={form.max_bookings_per_slot} onChange={(e) => setForm({ ...form, max_bookings_per_slot: e.target.value })} />
            </Field>
            <Field label="Daily limit" htmlFor="resource_daily_limit" hint="optional">
              <Input id="resource_daily_limit" type="number" min={0} value={form.daily_booking_limit} onChange={(e) => setForm({ ...form, daily_booking_limit: e.target.value })} />
            </Field>
          </div>
          <Field label="Effective from" htmlFor="resource_effective_from" hint="optional — blank means immediately" className="max-w-[220px]">
            <Input id="resource_effective_from" type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />
          </Field>

          <div className="flex justify-end gap-space-2">
            <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.name.trim()}>{saving ? "Saving…" : "Save resource"}</Button>
          </div>
        </div>
      )}

      {resources === null ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : resources.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No resources yet.</p>
      ) : (
        <ul className="divide-y divide-line">
          {resources.map((r) => {
            const expanded = expandedId === r.id;
            return (
              <li key={r.id} className="py-space-3">
                <div className="flex items-center justify-between gap-space-2">
                  <p className="text-[13.5px] font-semibold text-ink-900">{r.name}</p>
                  <div className="flex items-center gap-space-3">
                    {canManage && (
                      <button type="button" onClick={() => openEditForm(r)} className="text-ink-400 hover:text-ink-700" title="Edit resource">
                        <Pencil size={15} />
                      </button>
                    )}
                    <Badge tone={r.is_active ? "success" : "neutral"}>{r.is_active ? "Active" : "Inactive"}</Badge>
                    <button
                      type="button" onClick={() => handleToggleActive(r)} disabled={togglingId === r.id || !canManage}
                      role="switch" aria-checked={r.is_active}
                      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${r.is_active ? "bg-brand-600" : "bg-line"} ${togglingId === r.id ? "opacity-60" : ""}`}
                    >
                      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${r.is_active ? "translate-x-[22px]" : "translate-x-0.5"}`} />
                    </button>
                    <button type="button" onClick={() => setExpandedId(expanded ? null : r.id)} className="text-ink-400 hover:text-ink-700">
                      {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                  </div>
                </div>
                {expanded && (
                  <div className="mt-space-3 space-y-space-3">
                    <ResourceSlotManager resourceId={r.id} />
                    <ResourceLeaveManager resourceId={r.id} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
