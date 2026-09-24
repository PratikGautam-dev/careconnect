"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Trash2, Video, Calendar, Clock, Phone, User, Stethoscope, FileText, Tag } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Textarea } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/formatDate";
import { isPortalMutationError } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import {
  useAddVisitNote,
  useAppointmentDetail,
  useDeleteAppointmentDetail,
  useMarkAppointmentAttendance,
} from "@/hooks/useAppointmentDetail";
import {
  LAB_STATUS_LABELS,
  SOURCE_LABELS,
  STATUS_LABELS,
  STATUS_STYLES,
} from "../_components/appointments-columns";

function DetailRow({ label, value, icon: Icon }: { label: string; value: React.ReactNode; icon?: typeof Calendar }) {
  if (!value) return null;
  return (
    <div className="gap-space-3 flex items-center">
      {Icon && <Icon size={14} className="text-ink-400 shrink-0" />}
      <dt className="text-ink-400 text-[12.5px] font-medium w-28 shrink-0">{label}</dt>
      <dd className="text-ink-900 text-[13px]">{value}</dd>
    </div>
  );
}

function SectionTitle({ title, icon: Icon }: { title: string; icon?: typeof Calendar }) {
  return (
    <div className="mb-space-3 gap-space-2 flex items-center">
      {Icon && <Icon size={15} className="text-brand-600" />}
      <h3 className="text-label text-ink-900 font-semibold">{title}</h3>
    </div>
  );
}

export default function AppointmentDetailPage() {
  const { hospital, ready } = usePortalGuard();
  const params = useParams();
  const appointmentId = params.id as string;

  const { appointment, patient, notes, error, refetch } = useAppointmentDetail(
    appointmentId,
    ready,
  );
  const markAttendance = useMarkAppointmentAttendance();
  const { deleteAndRedirect, deleting } = useDeleteAppointmentDetail();
  const addVisitNote = useAddVisitNote();

  const [noteText, setNoteText] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);

  async function handleAttendance(attended: boolean) {
    try {
      await markAttendance.mutateAsync({ appointmentId, attended });
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't update attendance", err.message);
    }
  }

  function handleDelete() {
    deleteAndRedirect(appointmentId);
  }

  async function handleAddNote() {
    if (!noteText.trim() || !patient) return;
    setNoteError(null);
    try {
      await addVisitNote.mutateAsync({ patientId: patient.id, noteText: noteText.trim() });
      setNoteText("");
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) setNoteError(err.message);
    }
  }

  const isTele = appointment?.appointment_type_id === "tele";
  const canMarkAttendance = appointment && (appointment.status === "booked" || appointment.status === "attended" || appointment.status === "no_show");

  return (
    <PortalShell hospital={hospital} active="appointments">
      <Button href="/portal/appointments" variant="ghost" className="-ml-space-3 mb-space-4">
        <ArrowLeft size={14} /> Back to appointments
      </Button>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {!appointment ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <>
          <PageHeader
            title={appointment.patient_name || appointment.phone}
            description={
              appointment.reference_id ? `Reference ${appointment.reference_id}` : undefined
            }
            actions={
              <div className="gap-space-2 flex items-center">
                {(appointment.status !== "booked") && (
                  <PermissionGate
                    page={
                      appointment.procedure_id != null
                        ? "daycare_appointments"
                        : appointment.diagnostic_test_id != null
                          ? "diagnostic_appointments"
                          : "appointments"
                    }
                    action="delete"
                  >
                    <Button
                      variant="secondary"
                      onClick={handleDelete}
                      disabled={deleting}
                      className="border-error/30 text-error hover:border-error hover:bg-error/10"
                    >
                      <Trash2 size={14} /> Delete
                    </Button>
                  </PermissionGate>
                )}
              </div>
            }
          />

          <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
            {/* Left column - Appointment Overview & Actions */}
            <div className="lg:col-span-1 space-y-space-4">
              {/* Status & Quick Actions Card */}
              <Card className="p-space-4">
                <div className="gap-space-3 flex items-start justify-between">
                  <div>
                    <p className="text-ink-900 text-[16px] font-bold">
                      {appointment.patient_name || "—"}
                    </p>
                    <p className="text-ink-600 text-[12.5px]">{appointment.department_name}</p>
                  </div>
                  <span
                    className={cn(
                      "px-space-3 shrink-0 rounded-full py-1 text-[11.5px] font-semibold",
                      STATUS_STYLES[appointment.status] || "text-ink-600 bg-black/[0.04]",
                    )}
                  >
                    {STATUS_LABELS[appointment.status] || appointment.status}
                  </span>
                </div>

                <div className="mt-space-3 gap-space-2 border-line pt-space-3 border-t">
                  <DetailRow label="Scheduled" value={formatDateTime(appointment.scheduled_at)} icon={Calendar} />
                  <DetailRow label="Doctor" value={appointment.doctor_name} icon={Stethoscope} />
                  <DetailRow
                    label="Type"
                    value={
                      appointment.appointment_type_id
                        ? TYPE_LABELS[appointment.appointment_type_id] || appointment.appointment_type_id
                        : null
                    }
                    icon={Tag}
                  />
                </div>

                {isTele && appointment.video_link && (
                  <a
                    href={appointment.video_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-space-3 gap-space-2 bg-brand-600 px-space-4 py-space-3 hover:bg-brand-700 flex items-center justify-center rounded-md text-[13.5px] font-semibold text-white w-full"
                  >
                    <Video size={16} /> Join video consultation
                  </a>
                )}

                {canMarkAttendance && (
                  <div className="mt-space-3 gap-space-2 flex">
                    <Button
                      variant={appointment.status === "attended" ? "primary" : "secondary"}
                      onClick={() => handleAttendance(true)}
                      disabled={markAttendance.isPending}
                      className="flex-1"
                    >
                      Attended
                    </Button>
                    <Button
                      variant={appointment.status === "no_show" ? "primary" : "secondary"}
                      onClick={() => handleAttendance(false)}
                      disabled={markAttendance.isPending}
                      className="flex-1"
                    >
                      No-show
                    </Button>
                  </div>
                )}
              </Card>

              {/* Patient Demographics Card */}
              {patient && (
                <Card className="p-space-4">
                  <SectionTitle title="Patient Details" icon={User} />
                  <dl className="space-y-space-2 text-[13px]">
                    <DetailRow label="Phone" value={<span className="tabular-nums">{appointment.phone}</span>} icon={Phone} />
                    <DetailRow label="Patient ID" value={appointment.patient_display_id} />
                    <DetailRow label="MRN" value={patient.mrn} />
                    <DetailRow label="Date of birth" value={patient.date_of_birth} icon={Calendar} />
                    <DetailRow label="Gender" value={patient.gender} />
                  </dl>
                </Card>
              )}
            </div>

            {/* Right column - Appointment Details & Notes */}
            <div className="lg:col-span-2 space-y-space-4">
              {/* Appointment Details Card */}
              <Card className="p-space-4">
                <SectionTitle title="Appointment Details" icon={FileText} />
                <dl className="space-y-space-2 text-[13px]">
                  <DetailRow label="Booked at" value={appointment.created_at ? formatDateTime(appointment.created_at) : null} icon={Clock} />
                  <DetailRow label="Source" value={SOURCE_LABELS[appointment.source] || appointment.source} />
                  <DetailRow
                    label="Lab status"
                    value={
                      appointment.lab_status
                        ? LAB_STATUS_LABELS[appointment.lab_status] || appointment.lab_status
                        : null
                    }
                  />
                  <DetailRow label="Reference ID" value={appointment.reference_id} />
                </dl>
              </Card>

              {/* Visit Notes Card */}
              <Card className="p-space-4">
                <div className="mb-space-3 flex items-center justify-between">
                  <SectionTitle title="Visit Notes" icon={FileText} />
                </div>
                {patient ? (
                  <>
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
                    <Button
                      onClick={handleAddNote}
                      disabled={addVisitNote.isPending || !noteText.trim()}
                      size="md"
                      className="mt-space-2 w-full"
                    >
                      {addVisitNote.isPending ? "Saving…" : "Add note"}
                    </Button>

                    <div className="mt-space-4 space-y-space-3 border-line pt-space-4 border-t">
                      {notes.length === 0 ? (
                        <p className="text-hint text-center py-space-2">No visit notes yet.</p>
                      ) : (
                        notes.map((n) => (
                          <div key={n.id} className="bg-paper p-space-3 rounded-md">
                            <p className="text-ink-900 text-[13px] whitespace-pre-wrap">
                              {n.note_text}
                            </p>
                            <p className="mt-space-1 text-ink-400 text-[11px]">
                              {n.doctor_name || "Staff"} · {formatDateTime(n.created_at)}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </>
                ) : (
                  <p className="text-ink-400 text-[12.5px] text-center py-space-4">
                    This appointment isn&apos;t linked to a patient record, so notes can&apos;t be
                    added here.
                  </p>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </PortalShell>
  );
}
