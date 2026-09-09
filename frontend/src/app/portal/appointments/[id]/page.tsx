"use client";

import { useParams } from "next/navigation";
import { ArrowLeft, Trash2, Video } from "lucide-react";
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
import { TYPE_LABELS } from "@/hooks/useAppointments";
import { useAppointmentDetail } from "@/hooks/useAppointmentDetail";
import { LAB_STATUS_LABELS, SOURCE_LABELS, STATUS_LABELS, STATUS_STYLES } from "../_components/appointments-columns";

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-space-3">
      <dt className="text-ink-400">{label}</dt>
      <dd className="text-right text-ink-900">{value}</dd>
    </div>
  );
}

export default function AppointmentDetailPage() {
  const { hospital, ready } = usePortalGuard();
  const params = useParams();
  const appointmentId = params.id as string;

  const {
    appointment, patient, notes, error, marking, deleting,
    handleAttendance, handleDelete,
    noteText, setNoteText, savingNote, noteError, handleAddNote,
  } = useAppointmentDetail(appointmentId, ready);

  return (
    <PortalShell hospital={hospital} active="appointments">
      <Button href="/portal/appointments" variant="ghost" className="-ml-space-3 mb-space-4">
        <ArrowLeft size={14} /> Back to appointments
      </Button>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!appointment ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <>
          <PageHeader
            title={appointment.patient_name || appointment.phone}
            description={appointment.reference_id ? `Reference ${appointment.reference_id}` : undefined}
          />

          <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[1fr_1.4fr]">
            <div className="space-y-space-4">
              <Card className="p-space-5">
                <div className="mb-space-3 flex items-start justify-between gap-space-3">
                  <div>
                    <p className="text-[16px] font-bold text-ink-900">{appointment.patient_name || "—"}</p>
                    <p className="text-[12.5px] text-ink-600">{appointment.department_name}</p>
                  </div>
                  <span
                    className={cn(
                      "shrink-0 rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                      STATUS_STYLES[appointment.status] || "bg-black/[0.04] text-ink-600",
                    )}
                  >
                    {STATUS_LABELS[appointment.status] || appointment.status}
                  </span>
                </div>

                <dl className="space-y-space-2 text-[13px]">
                  <DetailRow label="Scheduled" value={formatDateTime(appointment.scheduled_at)} />
                  <DetailRow label="Booked" value={appointment.created_at ? formatDateTime(appointment.created_at) : null} />
                  <DetailRow label="Phone" value={<span className="tabular-nums">{appointment.phone}</span>} />
                  <DetailRow label="Patient ID" value={appointment.patient_display_id} />
                  <DetailRow label="MRN" value={patient?.mrn} />
                  <DetailRow label="Date of birth" value={patient?.date_of_birth} />
                  <DetailRow label="Gender" value={patient?.gender} />
                  <DetailRow label="Doctor" value={appointment.doctor_name} />
                  <DetailRow
                    label="Type"
                    value={
                      appointment.appointment_type_id
                        ? TYPE_LABELS[appointment.appointment_type_id] || appointment.appointment_type_id
                        : null
                    }
                  />
                  <DetailRow label="Source" value={SOURCE_LABELS[appointment.source] || appointment.source} />
                  <DetailRow
                    label="Lab status"
                    value={appointment.lab_status ? LAB_STATUS_LABELS[appointment.lab_status] || appointment.lab_status : null}
                  />
                  <DetailRow label="Reference" value={appointment.reference_id} />
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

                {appointment.status !== "booked" && (
                  <PermissionGate page="appointments" action="delete">
                    <div className="mt-space-4 border-t border-line pt-space-4">
                      <Button
                        variant="secondary"
                        onClick={handleDelete}
                        disabled={deleting}
                        className="w-full border-error/30 text-error hover:border-error hover:bg-error/10"
                      >
                        <Trash2 size={14} /> {deleting ? "Deleting…" : "Delete appointment"}
                      </Button>
                    </div>
                  </PermissionGate>
                )}
              </Card>
            </div>

            <div className="space-y-space-4">
              <Card className="p-space-5">
                <p className="text-label mb-space-3 font-semibold text-ink-900">Visit notes</p>
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
                    <Button onClick={handleAddNote} disabled={savingNote || !noteText.trim()} size="md">
                      {savingNote ? "Saving…" : "Add note"}
                    </Button>
                  </>
                ) : (
                  <p className="text-[12.5px] text-ink-400">
                    This appointment isn&apos;t linked to a patient record, so notes can&apos;t be added here.
                  </p>
                )}

                <div className="mt-space-5 space-y-space-3 border-t border-line pt-space-4">
                  {notes.length === 0 ? (
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
        </>
      )}
    </PortalShell>
  );
}
