"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Banknote, Trash2, Video, Calendar, User, FileText, Tag } from "lucide-react";
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
import { TYPE_LABELS, type Appointment } from "@/hooks/useAppointments";
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
import { RecordPaymentDialog } from "../_components/RecordPaymentDialog";

const PAYMENT_STATUS_LABELS: Record<string, string> = {
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
  pay_at_hospital: "Pay at Hospital",
};
const PAYMENT_STATUS_STYLES: Record<string, string> = {
  paid: "bg-success-tint text-success",
  pending: "bg-clay-100 text-clay-700",
  failed: "bg-error-tint text-error",
  pay_at_hospital: "bg-clay-100 text-clay-700",
};

function DetailRow({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  icon?: typeof Calendar;
}) {
  if (!value) return null;
  return (
    <div className="gap-space-3 flex items-center">
      {Icon && <Icon size={14} className="text-ink-400 shrink-0" />}
      <dt className="text-ink-400 w-28 shrink-0 text-[12.5px] font-medium">{label}</dt>
      <dd className="text-ink-900 text-[13px]">{value}</dd>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: typeof Calendar;
  children: React.ReactNode;
}) {
  return (
    <div className="border-line pt-space-4 mt-space-4 border-t first:mt-0 first:border-0 first:pt-0">
      <div className="mb-space-3 gap-space-2 flex items-center">
        {Icon && <Icon size={15} className="text-brand-600" />}
        <h3 className="text-label text-ink-900 font-semibold">{title}</h3>
      </div>
      {children}
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
  const [recordPaymentTarget, setRecordPaymentTarget] = useState<Appointment | null>(null);

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
  const canMarkAttendance =
    appointment &&
    (appointment.status === "booked" ||
      appointment.status === "attended" ||
      appointment.status === "no_show");

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

          <Card className="p-space-5 mx-auto">
            {/* Who + when + status -- the one thing worth knowing at a glance. */}
            <div className="gap-space-3 flex items-start justify-between">
              <div>
                <p className="text-ink-900 text-[17px] font-bold">
                  {appointment.patient_name || "—"}
                </p>
                <p className="text-ink-600 text-[12.5px]">
                  {appointment.department_name}
                  {appointment.doctor_name ? ` · ${appointment.doctor_name}` : ""}
                </p>
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

            {/* Schedule + type + payment -- the next most load-bearing facts. */}
            <div className="mt-space-3 gap-space-2 border-line pt-space-3 border-t">
              <DetailRow
                label="Scheduled"
                value={formatDateTime(appointment.scheduled_at)}
                icon={Calendar}
              />
              <DetailRow
                label="Type"
                value={
                  appointment.appointment_type_id
                    ? TYPE_LABELS[appointment.appointment_type_id] ||
                      appointment.appointment_type_id
                    : null
                }
                icon={Tag}
              />
              {appointment.payment_status && (
                <DetailRow
                  label="Payment"
                  icon={Banknote}
                  value={
                    <span
                      className={cn(
                        "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                        PAYMENT_STATUS_STYLES[appointment.payment_status],
                      )}
                    >
                      {PAYMENT_STATUS_LABELS[appointment.payment_status]}
                      {appointment.payment_amount != null &&
                        ` · ₹${appointment.payment_amount.toLocaleString("en-IN")}`}
                    </span>
                  }
                />
              )}
            </div>

            {/* Actions -- whatever's actionable RIGHT NOW, right under the facts
            that justify it, before anything read-only/historical below. */}
            {(isTele && appointment.video_link) ||
            (appointment.payment_status &&
              appointment.payment_status !== "paid" &&
              appointment.status !== "cancelled" &&
              appointment.status !== "rescheduled") ||
            canMarkAttendance ? (
              <div className="mt-space-3 gap-space-2 border-line pt-space-3 flex flex-wrap border-t">
                {isTele && appointment.video_link && (
                  <a
                    href={appointment.video_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="gap-space-2 bg-brand-600 px-space-4 py-space-3 hover:bg-brand-700 flex flex-1 items-center justify-center rounded-md text-[13.5px] font-semibold text-white"
                  >
                    <Video size={16} /> Join video consultation
                  </a>
                )}
                {appointment.payment_status &&
                  appointment.payment_status !== "paid" &&
                  appointment.status !== "cancelled" &&
                  appointment.status !== "rescheduled" && (
                    <PermissionGate page="appointments" action="write">
                      <Button
                        variant="secondary"
                        onClick={() => setRecordPaymentTarget(appointment)}
                        className="flex-1"
                      >
                        <Banknote size={14} /> Record payment
                      </Button>
                    </PermissionGate>
                  )}
                {canMarkAttendance && (
                  <>
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
                  </>
                )}
              </div>
            ) : null}

            {/* Patient demographics -- secondary reference info. */}
            {patient && (
              <Section title="Patient Details" icon={User}>
                <dl className="space-y-space-2">
                  <DetailRow
                    label="Phone"
                    value={<span className="tabular-nums">{appointment.phone}</span>}
                  />
                  <DetailRow label="Patient ID" value={appointment.patient_display_id} />
                  <DetailRow label="MRN" value={patient.mrn} />
                  <DetailRow label="Date of birth" value={patient.date_of_birth} />
                  <DetailRow label="Gender" value={patient.gender} />
                </dl>
              </Section>
            )}

            {/* Booking metadata -- rarely needed, kept but pushed further down. */}
            <Section title="Appointment Details" icon={FileText}>
              <dl className="space-y-space-2">
                <DetailRow
                  label="Booked at"
                  value={appointment.created_at ? formatDateTime(appointment.created_at) : null}
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
                <DetailRow label="Reference ID" value={appointment.reference_id} />
              </dl>
            </Section>

            {/* Visit notes -- the longest, most detailed content, last. */}
            <Section title="Visit Notes" icon={FileText}>
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
                      <p className="text-hint py-space-2 text-center">No visit notes yet.</p>
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
                <p className="text-ink-400 py-space-4 text-center text-[12.5px]">
                  This appointment isn&apos;t linked to a patient record, so notes can&apos;t be
                  added here.
                </p>
              )}
            </Section>
          </Card>
        </>
      )}

      <RecordPaymentDialog
        appointment={recordPaymentTarget}
        onOpenChange={(open) => !open && setRecordPaymentTarget(null)}
        onCollected={refetch}
      />
    </PortalShell>
  );
}
