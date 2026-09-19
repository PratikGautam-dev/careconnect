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
import {
  LAB_STATUS_LABELS,
  SOURCE_LABELS,
  STATUS_LABELS,
  STATUS_STYLES,
} from "../_components/appointments-columns";

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null;
  return (
    <div className="gap-space-3 flex justify-between">
      <dt className="text-ink-400">{label}</dt>
      <dd className="text-ink-900 text-right">{value}</dd>
    </div>
  );
}

export default function AppointmentDetailPage() {
  const { hospital, ready } = usePortalGuard();
  const params = useParams();
  const appointmentId = params.id as string;

  const {
    appointment,
    patient,
    notes,
    error,
    marking,
    deleting,
    handleAttendance,
    handleDelete,
    noteText,
    setNoteText,
    savingNote,
    noteError,
    handleAddNote,
  } = useAppointmentDetail(appointmentId, ready);

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
          />

          <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-[1fr_1.4fr]">
            <div className="space-y-space-4">
              <Card className="p-space-5">
                <div className="mb-space-3 gap-space-3 flex items-start justify-between">
                  <div>
                    <p className="text-ink-900 text-[16px] font-bold">
                      {appointment.patient_name || "—"}
                    </p>
                    <p className="text-ink-600 text-[12.5px]">{appointment.department_name}</p>
                  </div>
                  <span
                    className={cn(
                      "px-space-2 shrink-0 rounded-full py-0.5 text-[11px] font-semibold",
                      STATUS_STYLES[appointment.status] || "text-ink-600 bg-black/[0.04]",
                    )}
                  >
                    {STATUS_LABELS[appointment.status] || appointment.status}
                  </span>
                </div>

                <dl className="space-y-space-2 text-[13px]">
                  <DetailRow label="Scheduled" value={formatDateTime(appointment.scheduled_at)} />
                  <DetailRow
                    label="Booked"
                    value={appointment.created_at ? formatDateTime(appointment.created_at) : null}
                  />
                  <DetailRow
                    label="Phone"
                    value={<span className="tabular-nums">{appointment.phone}</span>}
                  />
                  <DetailRow label="Patient ID" value={appointment.patient_display_id} />
                  <DetailRow label="MRN" value={patient?.mrn} />
                  <DetailRow label="Date of birth" value={patient?.date_of_birth} />
                  <DetailRow label="Gender" value={patient?.gender} />
                  <DetailRow label="Doctor" value={appointment.doctor_name} />
                  <DetailRow
                    label="Type"
                    value={
                      appointment.appointment_type_id
                        ? TYPE_LABELS[appointment.appointment_type_id] ||
                          appointment.appointment_type_id
                        : null
                    }
                  />
                  <DetailRow
                    label="Source"
                    value={SOURCE_LABELS[appointment.source] || appointment.source}
                  />
                  <DetailRow
                    label="Lab status"
                    value={
                      appointment.lab_status
                        ? LAB_STATUS_LABELS[appointment.lab_status] || appointment.lab_status
                        : null
                    }
                  />
                  <DetailRow label="Reference" value={appointment.reference_id} />
                </dl>

                {appointment.appointment_type_id === "tele" && appointment.video_link && (
                  <a
                    href={appointment.video_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-space-4 gap-space-2 bg-brand-600 px-space-4 py-space-3 hover:bg-brand-700 flex items-center justify-center rounded-md text-[14px] font-semibold text-white"
                  >
                    <Video size={16} /> Join video consultation
                  </a>
                )}

                {(appointment.status === "booked" ||
                  appointment.status === "attended" ||
                  appointment.status === "no_show") && (
                  <div className="mt-space-4 gap-space-2 border-line pt-space-4 flex border-t">
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
                    <div className="mt-space-4 border-line pt-space-4 border-t">
                      <Button
                        variant="secondary"
                        onClick={handleDelete}
                        disabled={deleting}
                        className="border-error/30 text-error hover:border-error hover:bg-error/10 w-full"
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
                <p className="text-label mb-space-3 text-ink-900 font-semibold">Visit notes</p>
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
                      disabled={savingNote || !noteText.trim()}
                      size="md"
                    >
                      {savingNote ? "Saving…" : "Add note"}
                    </Button>
                  </>
                ) : (
                  <p className="text-ink-400 text-[12.5px]">
                    This appointment isn&apos;t linked to a patient record, so notes can&apos;t be
                    added here.
                  </p>
                )}

                <div className="mt-space-5 space-y-space-3 border-line pt-space-4 border-t">
                  {notes.length === 0 ? (
                    <p className="text-hint">No visit notes yet.</p>
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
              </Card>
            </div>
          </div>
        </>
      )}
    </PortalShell>
  );
}
