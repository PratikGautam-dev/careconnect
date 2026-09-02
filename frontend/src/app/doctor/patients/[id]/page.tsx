"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Video } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";
import { cn } from "@/lib/cn";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { staffFetch } from "@/lib/staffAuth";

type Patient = {
  id: number;
  phone: string;
  name: string | null;
  patient_display_id: string | null;
  mrn: string | null;
  date_of_birth: string | null;
  gender: string | null;
};

type Appointment = {
  id: number;
  phone: string;
  department_name: string;
  scheduled_at: string;
  status: string;
  reference_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
};

type VisitNote = {
  id: number;
  note_text: string;
  created_at: string;
};

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};
const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled", attended: "Attended", no_show: "No-show",
};

export default function DoctorPatientDetailPage() {
  const { doctor, ready } = useDoctorGuard();
  const router = useRouter();
  const params = useParams();
  const patientId = params.id as string;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [notes, setNotes] = useState<VisitNote[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch(`/api/doctor/patients/${patientId}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/doctor/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { patient: Patient | null; appointments: Appointment[]; notes: VisitNote[] };
    setPatient(data.patient);
    setAppointments(data.appointments);
    setNotes(data.notes);
  }, [patientId, router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="patients">
      <Link href="/doctor/patients" className="mb-space-4 inline-flex items-center gap-space-1 text-[13px] font-semibold text-brand-600 hover:underline">
        <ArrowLeft size={14} /> Back to patients
      </Link>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!appointments ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_1.4fr]">
          <div className="space-y-space-4">
            <Card className="p-space-5">
              <p className="text-[16px] font-bold text-ink-900">{patient?.name || patient?.patient_display_id || "Patient"}</p>
              <dl className="mt-space-3 space-y-space-2 text-[13px]">
                <div className="flex justify-between gap-space-3">
                  <dt className="text-ink-400">Phone</dt>
                  <dd className="tabular-nums text-ink-900">{patient?.phone}</dd>
                </div>
                {patient?.patient_display_id && (
                  <div className="flex justify-between gap-space-3">
                    <dt className="text-ink-400">Patient ID</dt>
                    <dd className="text-ink-900">{patient.patient_display_id}</dd>
                  </div>
                )}
                {patient?.mrn && (
                  <div className="flex justify-between gap-space-3">
                    <dt className="text-ink-400">MRN</dt>
                    <dd className="text-ink-900">{patient.mrn}</dd>
                  </div>
                )}
                {patient?.date_of_birth && (
                  <div className="flex justify-between gap-space-3">
                    <dt className="text-ink-400">Date of birth</dt>
                    <dd className="text-ink-900">{formatDate(patient.date_of_birth)}</dd>
                  </div>
                )}
                {patient?.gender && (
                  <div className="flex justify-between gap-space-3">
                    <dt className="text-ink-400">Gender</dt>
                    <dd className="text-ink-900">{patient.gender}</dd>
                  </div>
                )}
              </dl>
            </Card>

            <Card className="p-space-5">
              <p className="text-label mb-space-3 font-semibold text-ink-900">Visit notes I&apos;ve added</p>
              {notes === null ? (
                <p className="text-hint">Loading…</p>
              ) : notes.length === 0 ? (
                <p className="text-hint">No visit notes yet.</p>
              ) : (
                <div className="space-y-space-3">
                  {notes.map((n) => (
                    <div key={n.id} className="rounded-md bg-paper p-space-3">
                      <p className="whitespace-pre-wrap text-[13px] text-ink-900">{n.note_text}</p>
                      <p className="mt-space-1 text-[11px] text-ink-400">{formatShortDateTime(n.created_at)}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <Card className="p-space-5">
            <p className="text-label mb-space-3 font-semibold text-ink-900">Appointments with me</p>
            {appointments.length === 0 ? (
              <p className="text-hint">No appointments yet.</p>
            ) : (
              <div className="space-y-space-2">
                {appointments.map((a) => (
                  <Link key={a.id} href={`/doctor/appointments/${a.id}`}>
                    <div className="flex items-center gap-space-3 rounded-md border border-line bg-paper p-space-3 transition-colors duration-150 hover:border-brand-300">
                      <div className="w-36 shrink-0 text-[12.5px] text-ink-900">{formatShortDateTime(a.scheduled_at)}</div>
                      <div className="min-w-0 flex-1 truncate text-[12.5px] text-ink-600">{a.department_name}</div>
                      {a.reference_id && <span className="hidden shrink-0 text-[11px] text-ink-400 sm:inline">{a.reference_id}</span>}
                      {a.appointment_type_id === "tele" && a.video_link && (
                        <Video size={14} className="shrink-0 text-brand-600" />
                      )}
                      <span
                        className={cn(
                          "shrink-0 rounded-full px-space-2 py-0.5 text-[10.5px] font-semibold",
                          STATUS_STYLES[a.status] || "bg-black/[0.04] text-ink-600",
                        )}
                      >
                        {STATUS_LABELS[a.status] || a.status}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </DoctorShell>
  );
}
