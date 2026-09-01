"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Video } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Textarea } from "@/components/ui/Input";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";
import { cn } from "@/lib/cn";
import { staffFetch } from "@/lib/staffAuth";

type Appointment = {
  id: number;
  phone: string;
  department_name: string;
  scheduled_at: string;
  status: string;
  reference_id: string | null;
  patient_display_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
};

type Patient = {
  id: number;
  phone: string;
  name: string | null;
  patient_display_id: string | null;
  mrn: string | null;
  date_of_birth: string | null;
  gender: string | null;
};

type VisitNote = {
  id: number;
  note_text: string;
  created_at: string;
  doctor_name: string | null;
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

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export default function DoctorAppointmentDetailPage() {
  const { doctor, ready } = useDoctorGuard();
  const router = useRouter();
  const params = useParams();
  const appointmentId = params.id as string;

  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [notes, setNotes] = useState<VisitNote[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState(false);

  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch(`/api/doctor/appointments/${appointmentId}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/doctor/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { appointment: Appointment; patient: Patient | null; notes: VisitNote[] };
    setAppointment(data.appointment);
    setPatient(data.patient);
    setNotes(data.notes);
  }, [appointmentId, router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleAttendance(attended: boolean) {
    setMarking(true);
    const result = await staffFetch(`/api/doctor/appointments/${appointmentId}/attendance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attended }),
    });
    setMarking(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/doctor/login");
      else setError(result.error);
      return;
    }
    load();
  }

  async function handleAddNote() {
    if (!noteText.trim()) return;
    setSavingNote(true);
    setNoteError(null);
    const result = await staffFetch(`/api/doctor/appointments/${appointmentId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_text: noteText.trim() }),
    });
    setSavingNote(false);
    if (!result.ok) {
      setNoteError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNoteText("");
    load();
  }

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="dashboard">
      <Link href="/doctor/dashboard" className="mb-space-4 inline-flex items-center gap-space-1 text-[13px] font-semibold text-brand-600 hover:underline">
        <ArrowLeft size={14} /> Back to today
      </Link>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!appointment ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_1.4fr]">
          <div className="space-y-space-4">
            <Card className="p-space-5">
              <div className="mb-space-3 flex items-start justify-between gap-space-3">
                <div>
                  <p className="text-[16px] font-bold text-ink-900">{patient?.name || patient?.patient_display_id || appointment.phone}</p>
                  <p className="text-[12.5px] text-ink-600">{appointment.department_name}</p>
                </div>
                <span className={cn("shrink-0 rounded-full px-space-2 py-0.5 text-[11px] font-semibold", STATUS_STYLES[appointment.status] || "bg-black/[0.04] text-ink-600")}>
                  {STATUS_LABELS[appointment.status] || appointment.status}
                </span>
              </div>

              <dl className="space-y-space-2 text-[13px]">
                <div className="flex justify-between gap-space-3">
                  <dt className="text-ink-400">Scheduled</dt>
                  <dd className="text-ink-900">{formatDateTime(appointment.scheduled_at)}</dd>
                </div>
                <div className="flex justify-between gap-space-3">
                  <dt className="text-ink-400">Phone</dt>
                  <dd className="tabular-nums text-ink-900">{appointment.phone}</dd>
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
                    <dd className="text-ink-900">{patient.date_of_birth}</dd>
                  </div>
                )}
                {patient?.gender && (
                  <div className="flex justify-between gap-space-3">
                    <dt className="text-ink-400">Gender</dt>
                    <dd className="text-ink-900">{patient.gender}</dd>
                  </div>
                )}
                {appointment.reference_id && (
                  <div className="flex justify-between gap-space-3">
                    <dt className="text-ink-400">Reference</dt>
                    <dd className="text-ink-900">{appointment.reference_id}</dd>
                  </div>
                )}
              </dl>

              {appointment.appointment_type_id === "tele" && appointment.video_link && (
                <a
                  href={appointment.video_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-space-4 flex items-center justify-center gap-space-2 rounded-md bg-brand-600 px-space-4 py-space-3 text-[14px] font-semibold text-white hover:bg-brand-700"
                >
                  <Video size={16} /> Join video consultation
                </a>
              )}

              {(appointment.status === "booked" || appointment.status === "attended" || appointment.status === "no_show") && (
                <div className="mt-space-4 flex gap-space-2 border-t border-line pt-space-4">
                  <Button
                    variant={appointment.status === "attended" ? "primary" : "secondary"}
                    onClick={() => handleAttendance(true)}
                    disabled={marking}
                    className="flex-1"
                  >
                    Attended
                  </Button>
                  <Button
                    variant={appointment.status === "no_show" ? "primary" : "secondary"}
                    onClick={() => handleAttendance(false)}
                    disabled={marking}
                    className="flex-1"
                  >
                    No-show
                  </Button>
                </div>
              )}
            </Card>
          </div>

          <div className="space-y-space-4">
            <Card className="p-space-5">
              <p className="text-label mb-space-3 font-semibold text-ink-900">Visit notes</p>
              <Field htmlFor="note_text" error={noteError || undefined}>
                <Textarea
                  id="note_text"
                  rows={3}
                  placeholder="Add a note about this visit…"
                  value={noteText}
                  invalid={!!noteError}
                  onChange={(e) => setNoteText(e.target.value)}
                />
              </Field>
              <Button onClick={handleAddNote} disabled={savingNote || !noteText.trim()} size="md">
                {savingNote ? "Saving…" : "Add note"}
              </Button>

              <div className="mt-space-5 space-y-space-3 border-t border-line pt-space-4">
                {notes === null ? (
                  <p className="text-hint">Loading…</p>
                ) : notes.length === 0 ? (
                  <p className="text-hint">No visit notes yet.</p>
                ) : (
                  notes.map((n) => (
                    <div key={n.id} className="rounded-md bg-paper p-space-3">
                      <p className="whitespace-pre-wrap text-[13px] text-ink-900">{n.note_text}</p>
                      <p className="mt-space-1 text-[11px] text-ink-400">
                        {n.doctor_name || "Staff"} · {formatDateTime(n.created_at)}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      )}
    </DoctorShell>
  );
}
