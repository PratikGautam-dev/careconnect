"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

type Department = { id: string; name: string };
type Doctor = { id: string; department_id: string; department_name: string; name: string; specialization: string | null };

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function emptyDoctorForm() {
  return {
    department_id: "",
    name: "",
    specialization: "",
    qualification: "",
    years_experience: "",
    working_days: [] as string[],
    shift1_start: "",
    shift1_end: "",
    slot_duration_minutes: "",
    break1_start: "",
    break1_end: "",
    max_bookings_per_slot: "1",
    daily_booking_limit: "",
  };
}

export default function PortalDoctorsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const [departments, setDepartments] = useState<Department[] | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newDeptName, setNewDeptName] = useState("");
  const [addingDept, setAddingDept] = useState(false);
  const [showDoctorForm, setShowDoctorForm] = useState(false);
  const [doctorForm, setDoctorForm] = useState(emptyDoctorForm());
  const [doctorErrors, setDoctorErrors] = useState<string[]>([]);
  const [savingDoctor, setSavingDoctor] = useState(false);

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
      load();
    }
  }

  function toggleDay(day: string) {
    setDoctorForm((f) => ({
      ...f,
      working_days: f.working_days.includes(day) ? f.working_days.filter((d) => d !== day) : [...f.working_days, day],
    }));
  }

  async function handleAddDoctor(e: React.FormEvent) {
    e.preventDefault();
    setSavingDoctor(true);
    setDoctorErrors([]);
    const working_hours = doctorForm.shift1_start && doctorForm.shift1_end ? [`${doctorForm.shift1_start}-${doctorForm.shift1_end}`] : [];
    const breaks = doctorForm.break1_start && doctorForm.break1_end ? [`${doctorForm.break1_start}-${doctorForm.break1_end}`] : [];
    const result = await portalFetch("/api/portal/doctors", {
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
      }),
    });
    setSavingDoctor(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setDoctorErrors([result.error]);
      return;
    }
    const data = result.data as { errors?: string[] };
    if (data.errors?.length) {
      setDoctorErrors(data.errors);
      return;
    }
    setDoctorForm(emptyDoctorForm());
    setShowDoctorForm(false);
    load();
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <PortalSidebar hospital={hospital} active="doctors" />
      <main className="flex-1 overflow-y-auto p-space-6">
        <h1 className="text-display mb-space-5">Doctors &amp; departments</h1>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        {!departments ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_320px]">
            <Card className="p-space-4">
              <div className="mb-space-3 flex items-center justify-between">
                <h3 className="text-label font-bold text-ink-900">Doctors</h3>
                <Button size="md" onClick={() => setShowDoctorForm((v) => !v)} disabled={departments.length === 0}>
                  <Plus size={14} /> Add doctor
                </Button>
              </div>

              {departments.length === 0 && (
                <p className="mb-space-3 text-[12.5px] text-ink-400">Add a department first, then you can add doctors to it.</p>
              )}

              {showDoctorForm && (
                <form onSubmit={handleAddDoctor} className="mb-space-4 rounded-lg border border-line bg-paper p-space-4">
                  {doctorErrors.length > 0 && (
                    <div className="mb-space-3 rounded-md border border-error bg-error-tint p-space-3 text-[12.5px] text-error">
                      <ul className="list-disc pl-space-4">
                        {doctorErrors.map((e, i) => (
                          <li key={i}>{e}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
                    <Field label="Department" htmlFor="department_id" required>
                      <select
                        id="department_id"
                        required
                        value={doctorForm.department_id}
                        onChange={(e) => setDoctorForm({ ...doctorForm, department_id: e.target.value })}
                        className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900"
                      >
                        <option value="">Choose…</option>
                        {departments.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Name" htmlFor="doc_name" required>
                      <Input id="doc_name" required value={doctorForm.name} onChange={(e) => setDoctorForm({ ...doctorForm, name: e.target.value })} />
                    </Field>
                    <Field label="Specialization" htmlFor="doc_spec">
                      <Input id="doc_spec" value={doctorForm.specialization} onChange={(e) => setDoctorForm({ ...doctorForm, specialization: e.target.value })} />
                    </Field>
                    <Field label="Qualification" htmlFor="doc_qual">
                      <Input id="doc_qual" value={doctorForm.qualification} onChange={(e) => setDoctorForm({ ...doctorForm, qualification: e.target.value })} />
                    </Field>
                  </div>

                  <Field label="Working days">
                    <div className="flex flex-wrap gap-space-2">
                      {WEEKDAYS.map((day) => {
                        const on = doctorForm.working_days.includes(day);
                        return (
                          <button
                            type="button"
                            key={day}
                            onClick={() => toggleDay(day)}
                            className={cn(
                              "flex h-8 w-11 items-center justify-center rounded-md border text-[12.5px] font-semibold",
                              on ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600",
                            )}
                          >
                            {day}
                          </button>
                        );
                      })}
                    </div>
                  </Field>

                  <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
                    <Field label="Working hours">
                      <div className="flex items-center gap-space-2">
                        <Input type="time" value={doctorForm.shift1_start} onChange={(e) => setDoctorForm({ ...doctorForm, shift1_start: e.target.value })} />
                        <span className="text-[12.5px] text-ink-400">to</span>
                        <Input type="time" value={doctorForm.shift1_end} onChange={(e) => setDoctorForm({ ...doctorForm, shift1_end: e.target.value })} />
                      </div>
                    </Field>
                    <Field label="Slot duration (minutes)" htmlFor="doc_duration">
                      <Input id="doc_duration" type="number" min={1} value={doctorForm.slot_duration_minutes} onChange={(e) => setDoctorForm({ ...doctorForm, slot_duration_minutes: e.target.value })} />
                    </Field>
                    <Field label="Break (optional)">
                      <div className="flex items-center gap-space-2">
                        <Input type="time" value={doctorForm.break1_start} onChange={(e) => setDoctorForm({ ...doctorForm, break1_start: e.target.value })} />
                        <span className="text-[12.5px] text-ink-400">to</span>
                        <Input type="time" value={doctorForm.break1_end} onChange={(e) => setDoctorForm({ ...doctorForm, break1_end: e.target.value })} />
                      </div>
                    </Field>
                    <Field label="Daily booking limit (optional)" htmlFor="doc_limit">
                      <Input id="doc_limit" type="number" min={0} value={doctorForm.daily_booking_limit} onChange={(e) => setDoctorForm({ ...doctorForm, daily_booking_limit: e.target.value })} />
                    </Field>
                  </div>

                  <div className="mt-space-3 flex gap-space-2">
                    <Button type="submit" disabled={savingDoctor}>
                      {savingDoctor ? "Saving…" : "Save doctor"}
                    </Button>
                    <Button type="button" variant="secondary" onClick={() => setShowDoctorForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </form>
              )}

              {doctors.length === 0 ? (
                <p className="py-space-4 text-center text-[13px] text-ink-400">No doctors yet.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {doctors.map((doc) => (
                    <li key={doc.id} className="flex items-center justify-between py-space-3">
                      <div>
                        <p className="text-[13.5px] font-semibold text-ink-900">{doc.name}</p>
                        <p className="text-[12px] text-ink-600">
                          {doc.department_name}
                          {doc.specialization ? ` · ${doc.specialization}` : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-space-4">
              <h3 className="text-label mb-space-3 font-bold text-ink-900">Departments</h3>
              <form onSubmit={handleAddDepartment} className="mb-space-3 flex gap-space-2">
                <Input placeholder="New department" value={newDeptName} onChange={(e) => setNewDeptName(e.target.value)} />
                <Button type="submit" size="md" disabled={addingDept || !newDeptName.trim()}>
                  <Plus size={14} />
                </Button>
              </form>
              {departments.length === 0 ? (
                <p className="text-[12.5px] text-ink-400">No departments yet.</p>
              ) : (
                <ul className="space-y-space-1">
                  {departments.map((d) => (
                    <li key={d.id} className="rounded-md bg-paper px-space-3 py-space-2 text-[13px] text-ink-900">
                      {d.name}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
