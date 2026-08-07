"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Plus, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { DoctorScheduleForm, DoctorScheduleFormState, emptyDoctorScheduleForm } from "@/components/portal/DoctorScheduleForm";
import { DoctorLeaveManager } from "@/components/portal/DoctorLeaveManager";
import { DoctorCsvImport } from "@/components/portal/DoctorCsvImport";
import { portalFetch } from "@/lib/portalAuth";

type Department = { id: string; name: string };
type Doctor = {
  id: string;
  department_id: string;
  department_name: string;
  name: string;
  specialization: string | null;
  is_active: boolean;
};

export default function PortalDoctorsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
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

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

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

  async function handleSaveDoctor() {
    setSavingDoctor(true);
    setDoctorErrors([]);
    const working_hours = doctorForm.shifts
      .filter((s) => s.start && s.end)
      .map((s) => `${s.start}-${s.end}`);
    const breaks = doctorForm.breaks
      .filter((b) => b && b.start && b.end)
      .map((b) => `${b.start}-${b.end}`);
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
        online_quota: doctorForm.online_quota,
        walkin_quota: doctorForm.walkin_quota,
        followup_duration_minutes: doctorForm.followup_duration_minutes,
        effective_from: doctorForm.effective_from,
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
    setDoctorForm(emptyDoctorScheduleForm());
    setShowDoctorForm(false);
    load();
  }

  async function handleToggleActive(doc: Doctor) {
    setTogglingId(doc.id);
    const result = await portalFetch(`/api/portal/doctors/${doc.id}/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !doc.is_active }),
    });
    setTogglingId(null);
    if (result.ok) load();
  }

  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <PortalSidebar hospital={hospital} active="doctors" />
      <main className="flex-1 overflow-y-auto p-space-6">
        <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
          <h1 className="text-display">Doctors &amp; departments</h1>
          {departments && departments.length > 0 && (
            <div className="flex gap-space-2">
              <Button
                variant="secondary"
                size="md"
                onClick={() => {
                  setShowCsvImport((v) => !v);
                  setShowDoctorForm(false);
                }}
              >
                <Upload size={14} /> Bulk import
              </Button>
              <Button
                size="md"
                onClick={() => {
                  setShowDoctorForm((v) => !v);
                  setShowCsvImport(false);
                  setDoctorForm(emptyDoctorScheduleForm());
                  setDoctorErrors([]);
                }}
              >
                <Plus size={14} /> Add doctor
              </Button>
            </div>
          )}
        </div>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        {!departments ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_320px]">
            <div className="space-y-space-4">
              {departments.length === 0 && (
                <Card className="p-space-4">
                  <p className="text-[12.5px] text-ink-400">Add a department first, then you can add doctors to it.</p>
                </Card>
              )}

              {showCsvImport && <DoctorCsvImport onImported={() => { load(); }} />}

              {showDoctorForm && (
                <DoctorScheduleForm
                  departments={departments}
                  value={doctorForm}
                  onChange={setDoctorForm}
                  onSave={handleSaveDoctor}
                  onCancel={() => setShowDoctorForm(false)}
                  saving={savingDoctor}
                  errors={doctorErrors}
                />
              )}

              <Card className="p-space-4">
                <h3 className="text-label mb-space-3 font-bold text-ink-900">Doctors</h3>
                {doctors.length === 0 ? (
                  <p className="py-space-4 text-center text-[13px] text-ink-400">No doctors yet.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {doctors.map((doc) => {
                      const expanded = expandedId === doc.id;
                      return (
                        <li key={doc.id} className="py-space-3">
                          <div className="flex items-center justify-between gap-space-3">
                            <div className="flex items-center gap-space-3">
                              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[13px] font-bold text-brand-700">
                                {doc.name.trim().charAt(0).toUpperCase() || "?"}
                              </div>
                              <div>
                                <p className="text-[13.5px] font-semibold text-ink-900">{doc.name}</p>
                                <p className="text-[12px] text-ink-600">
                                  {doc.department_name}
                                  {doc.specialization ? ` · ${doc.specialization}` : ""}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-space-3">
                              <Badge tone={doc.is_active ? "success" : "neutral"}>
                                {doc.is_active ? "Available" : "Unavailable"}
                              </Badge>
                              <button
                                type="button"
                                onClick={() => handleToggleActive(doc)}
                                disabled={togglingId === doc.id}
                                role="switch"
                                aria-checked={doc.is_active}
                                className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${
                                  doc.is_active ? "bg-brand-600" : "bg-line"
                                } ${togglingId === doc.id ? "opacity-60" : ""}`}
                              >
                                <span
                                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${
                                    doc.is_active ? "translate-x-[22px]" : "translate-x-0.5"
                                  }`}
                                />
                              </button>
                              <button
                                type="button"
                                onClick={() => setExpandedId(expanded ? null : doc.id)}
                                className="text-ink-400 hover:text-ink-700"
                              >
                                {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                              </button>
                            </div>
                          </div>
                          {expanded && (
                            <div className="mt-space-3">
                              <DoctorLeaveManager doctorId={doc.id} />
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Card>
            </div>

            <Card className="h-fit p-space-4">
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
