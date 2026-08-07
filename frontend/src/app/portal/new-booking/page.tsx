"use client";

import { useCallback, useEffect, useState } from "react";
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
type Doctor = { id: string; name: string };
type Slot = { id: string; label: string };
type Context = {
  departments: Department[];
  doctors_by_department: Record<string, Doctor[]>;
  slots_by_doctor: Record<string, Record<string, Slot[]>>;
};

export default function NewBookingPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const [ctx, setCtx] = useState<Context | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [date, setDate] = useState("");
  const [slotId, setSlotId] = useState("");

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/new-booking/context");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setCtx(result.data as Context);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  const doctors = departmentId && ctx ? ctx.doctors_by_department[departmentId] || [] : [];
  const datesForDoctor = doctorId && ctx ? Object.keys(ctx.slots_by_doctor[doctorId] || {}).sort() : [];
  const slotsForDate = doctorId && date && ctx ? ctx.slots_by_doctor[doctorId]?.[date] || [] : [];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErrors([]);
    const result = await portalFetch("/api/portal/new-booking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_name: patientName, patient_phone: patientPhone, department_id: departmentId, doctor_id: doctorId, slot_id: slotId }),
    });
    setSubmitting(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setErrors([result.error]);
      return;
    }
    const data = result.data as { errors?: string[] };
    if (data.errors?.length) {
      setErrors(data.errors);
      return;
    }
    setSuccess(true);
  }

  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <PortalSidebar hospital={hospital} active="appointments" />
      <main className="flex-1 overflow-y-auto p-space-6">
        <h1 className="text-display mb-space-5">New booking</h1>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <Card className="max-w-xl p-space-5">
          {success ? (
            <div className="text-center">
              <p className="mb-space-3 text-[14px] font-semibold text-success">Booking created.</p>
              <Button href="/portal/appointments">View appointments</Button>
            </div>
          ) : !ctx ? (
            <p className="text-[13px] text-ink-400">Loading…</p>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
                <Field label="Patient name (optional)" htmlFor="patient_name">
                  <Input id="patient_name" value={patientName} onChange={(e) => setPatientName(e.target.value)} />
                </Field>
                <Field label="Patient phone" htmlFor="patient_phone" required>
                  <Input id="patient_phone" required value={patientPhone} onChange={(e) => setPatientPhone(e.target.value)} />
                </Field>
              </div>

              <Field label="Branch" htmlFor="branch" hint="Single-location hospital — nothing to choose yet.">
                <select id="branch" disabled className="h-11 w-full cursor-not-allowed rounded-md border border-line bg-paper px-space-3 text-[14px] text-ink-600">
                  <option>Main Branch — {hospital?.name}</option>
                </select>
              </Field>

              <Field label="Department" htmlFor="department" required>
                <select
                  id="department"
                  required
                  value={departmentId}
                  onChange={(e) => {
                    setDepartmentId(e.target.value);
                    setDoctorId("");
                    setDate("");
                    setSlotId("");
                  }}
                  className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900"
                >
                  <option value="">Choose…</option>
                  {ctx.departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </Field>

              {departmentId && (
                <Field label="Doctor" htmlFor="doctor" required>
                  <select
                    id="doctor"
                    required
                    value={doctorId}
                    onChange={(e) => {
                      setDoctorId(e.target.value);
                      setDate("");
                      setSlotId("");
                    }}
                    className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900"
                  >
                    <option value="">Choose…</option>
                    {doctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </Field>
              )}

              {doctorId && (
                <Field label="Date">
                  {datesForDoctor.length === 0 ? (
                    <p className="text-[12.5px] text-ink-400">No available dates for this doctor.</p>
                  ) : (
                    <div className="flex flex-wrap gap-space-2">
                      {datesForDoctor.map((d) => (
                        <button
                          type="button"
                          key={d}
                          onClick={() => {
                            setDate(d);
                            setSlotId("");
                          }}
                          className={cn(
                            "rounded-md border px-space-3 py-space-2 text-[12.5px] font-semibold",
                            date === d ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600",
                          )}
                        >
                          {d}
                        </button>
                      ))}
                    </div>
                  )}
                </Field>
              )}

              {date && (
                <Field label="Time slot" required>
                  {slotsForDate.length === 0 ? (
                    <p className="text-[12.5px] text-ink-400">No slots available on this date.</p>
                  ) : (
                    <div className="flex flex-wrap gap-space-2">
                      {slotsForDate.map((s) => (
                        <button
                          type="button"
                          key={s.id}
                          onClick={() => setSlotId(s.id)}
                          className={cn(
                            "rounded-md border px-space-3 py-space-2 text-[12.5px] font-semibold",
                            slotId === s.id ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600",
                          )}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  )}
                </Field>
              )}

              {errors.length > 0 && (
                <div className="mb-space-3 rounded-md border border-error bg-error-tint p-space-3 text-[12.5px] text-error">
                  <ul className="list-disc pl-space-4">
                    {errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}

              <Button type="submit" disabled={submitting || !slotId} className="mt-space-2">
                {submitting ? "Booking…" : "Create booking"}
              </Button>
            </form>
          )}
        </Card>
      </main>
    </div>
  );
}
