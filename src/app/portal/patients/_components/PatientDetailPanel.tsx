"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Calendar,
  CalendarPlus,
  Cake,
  ExternalLink,
  FileText,
  Heart,
  MessageCircle,
  MoreHorizontal,
  Phone,
  Send,
  Stethoscope,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { QuickActionList, type QuickAction } from "@/components/portal/QuickActions";
import { cn } from "@/lib/cn";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import { usePatientSummary } from "@/hooks/usePatientSummary";
import type { Patient } from "@/hooks/usePatients";
import { AVATAR_TINTS, STATUS_LABELS, STATUS_STYLES, initials } from "./patients-columns";

const VISIT_STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};
const VISIT_STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed",
  cancelled: "Cancelled",
  rescheduled: "Rescheduled",
  attended: "Attended",
  no_show: "No-show",
};
const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  prescription: "Prescription",
  lab_report: "Lab Report",
  diagnostic_report: "Diagnostic Report",
  other: "Other",
};

const TABS = ["Overview", "Medical History", "Appointments", "Reports"] as const;
type Tab = (typeof TABS)[number];

function Section({
  icon: Icon,
  title,
  editHref,
  children,
}: {
  icon: typeof Cake;
  title: string;
  editHref?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-line p-space-3 rounded-md border">
      <div className="mb-space-2 flex items-center justify-between">
        <p className="gap-space-2 text-ink-900 flex items-center text-[12px] font-bold">
          <Icon size={13} className="text-brand-600" /> {title}
        </p>
        {editHref && (
          <Link
            href={editHref}
            className="text-brand-600 text-[11px] font-semibold hover:underline"
          >
            Edit
          </Link>
        )}
      </div>
      {children}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-[12.5px]">
      <span className="text-ink-400">{label}</span>
      <span className="text-ink-900 font-medium">{value}</span>
    </div>
  );
}

type Props = {
  patient: Patient | null;
  index: number;
  onBookAppointment: () => void;
};

/** Right-rail "selected patient" panel: avatar/status header, Overview/
 * Medical History/Appointments/Reports tabs. Overview only shows fields
 * this schema tracks (DOB/gender/phone/address) -- Blood Group, Marital
 * Status, Email, and Allergies/Current Diagnosis show "—" since there's no
 * column for them. The other 3 tabs are read-only previews of this
 * patient's real notes/visits/documents (via usePatientSummary); editing
 * stays on the full /portal/patients/[id] page. */
export function PatientDetailPanel({ patient, index, onBookAppointment }: Props) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("Overview");
  const { data: summary, loading } = usePatientSummary(patient?.id ?? null);

  if (!patient) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          Select a patient to view their profile.
        </p>
      </Card>
    );
  }

  const address = summary?.patient.address ?? null;
  const latestVisit = summary?.visit_history[0] ?? null;

  const quickActions: QuickAction[] = [
    { label: "Book Appointment", icon: CalendarPlus, onClick: onBookAppointment },
    { label: "View Reports", icon: FileText, onClick: () => setTab("Reports") },
    {
      label: "Send Message",
      icon: MessageCircle,
      disabled: true,
      title: "Coming soon — no patient-facing internal messaging exists yet",
    },
  ];

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex flex-col items-center text-center">
        <span
          className={cn(
            "mb-space-2 flex h-16 w-16 items-center justify-center rounded-full text-[20px] font-bold",
            AVATAR_TINTS[index % AVATAR_TINTS.length],
          )}
        >
          {initials(patient.name)}
        </span>
        <span
          className={cn(
            "mb-space-1 px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
            STATUS_STYLES[patient.status],
          )}
        >
          {STATUS_LABELS[patient.status]}
        </span>
        <p className="text-ink-900 text-[15px] font-bold">{patient.name || "—"}</p>
        <p className="text-ink-400 text-[12px]">
          Patient ID: {patient.patient_display_id || `#${patient.id}`}
        </p>
        {(patient.age != null || patient.gender) && (
          <p className="text-ink-400 text-[12px]">
            {patient.age != null ? `${patient.age} years` : ""}
            {patient.age != null && patient.gender ? ", " : ""}
            {patient.gender || ""}
          </p>
        )}
      </div>

      <div className="mb-space-3 gap-space-1 border-line flex overflow-x-auto border-b">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "px-space-2 pb-space-2 shrink-0 border-b-2 text-[12px] font-semibold whitespace-nowrap",
              tab === t
                ? "border-brand-600 text-brand-700"
                : "text-ink-400 hover:text-ink-600 border-transparent",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && (
        <div className="space-y-space-3">
          <Section icon={Cake} title="Demographics" editHref={`/portal/patients/${patient.id}`}>
            <div className="space-y-space-1">
              <Field label="Date of Birth" value={formatDate(patient.date_of_birth)} />
              <Field label="Gender" value={patient.gender || "—"} />
              <Field label="Blood Group" value="—" />
              <Field label="Marital Status" value="—" />
            </div>
          </Section>

          <Section
            icon={Phone}
            title="Contact Information"
            editHref={`/portal/patients/${patient.id}`}
          >
            <div className="space-y-space-1">
              <Field label="Phone" value={patient.phone} />
              <Field label="Email" value="—" />
              <Field label="Address" value={address || "—"} />
            </div>
          </Section>

          <Section icon={AlertTriangle} title="Allergies">
            <p className="text-ink-400 text-[12px]">Not tracked in this app yet.</p>
          </Section>

          <Section icon={Heart} title="Current Diagnosis">
            <p className="text-ink-400 text-[12px]">Not tracked in this app yet.</p>
          </Section>

          <Section icon={Calendar} title="Latest Visit">
            {loading ? (
              <p className="text-ink-400 text-[12px]">Loading…</p>
            ) : latestVisit ? (
              <>
                <p className="text-ink-900 text-[13px] font-semibold">
                  {formatDate(latestVisit.scheduled_at)}
                </p>
                <p className="mb-space-1 text-ink-600 text-[12px]">
                  Dr. {latestVisit.doctor_name} ({latestVisit.department_name})
                </p>
                <button
                  type="button"
                  onClick={() => setTab("Appointments")}
                  className="text-brand-600 text-[11px] font-semibold hover:underline"
                >
                  View All
                </button>
              </>
            ) : (
              <p className="text-ink-400 text-[12px]">No visits yet.</p>
            )}
          </Section>

          <div className="border-line pt-space-3 border-t">
            <p className="text-label mb-space-2 text-ink-900 font-bold">Quick Actions</p>
            <QuickActionList actions={quickActions} columns={2} size="sm">
              <DropdownMenu>
                <DropdownMenuTrigger className="gap-space-2 px-space-3 py-space-2 text-ink-900 hover:bg-brand-50 hover:text-brand-700 flex w-full items-center justify-center rounded-md text-[12.5px] font-semibold">
                  <MoreHorizontal size={14} /> More
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuGroup>
                    <DropdownMenuItem onClick={() => router.push(`/portal/patients/${patient.id}`)}>
                      <ExternalLink size={14} /> Open full record
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </QuickActionList>
          </div>
        </div>
      )}

      {tab === "Medical History" && (
        <div className="space-y-space-2">
          {loading ? (
            <p className="text-ink-400 text-[12px]">Loading…</p>
          ) : (summary?.notes.length ?? 0) === 0 ? (
            <p className="py-space-3 text-ink-400 text-center text-[12.5px]">
              No notes recorded yet.
            </p>
          ) : (
            summary!.notes.map((n) => (
              <div key={n.id} className="border-line p-space-2 rounded-md border">
                <div className="mb-space-1 text-ink-400 flex items-center justify-between text-[11px]">
                  <span className="flex items-center gap-1">
                    <Stethoscope size={11} /> {n.doctor_name || "Staff"}
                  </span>
                  <span>{formatShortDateTime(n.created_at)}</span>
                </div>
                <p className="text-ink-900 text-[12.5px]">{n.note_text}</p>
              </div>
            ))
          )}
          <Link
            href={`/portal/patients/${patient.id}`}
            className="text-brand-600 block text-center text-[11px] font-semibold hover:underline"
          >
            Add or manage notes on the full record
          </Link>
        </div>
      )}

      {tab === "Appointments" && (
        <div className="space-y-space-2">
          {loading ? (
            <p className="text-ink-400 text-[12px]">Loading…</p>
          ) : (summary?.visit_history.length ?? 0) === 0 ? (
            <p className="py-space-3 text-ink-400 text-center text-[12.5px]">
              No appointments yet.
            </p>
          ) : (
            summary!.visit_history.slice(0, 8).map((v) => (
              <div
                key={v.id}
                className="border-line p-space-2 flex items-center justify-between rounded-md border"
              >
                <div className="min-w-0">
                  <p className="text-ink-900 truncate text-[12.5px] font-semibold">
                    {v.appointment_type_id
                      ? TYPE_LABELS[v.appointment_type_id] || "Appointment"
                      : "Appointment"}
                  </p>
                  <p className="text-ink-400 truncate text-[11px]">
                    {formatShortDateTime(v.scheduled_at)} · Dr. {v.doctor_name}
                  </p>
                </div>
                <span
                  className={cn(
                    "px-space-2 shrink-0 rounded-full py-0.5 text-[10.5px] font-semibold",
                    VISIT_STATUS_STYLES[v.status] || "text-ink-600 bg-black/4",
                  )}
                >
                  {VISIT_STATUS_LABELS[v.status] || v.status}
                </span>
              </div>
            ))
          )}
          <Link
            href={`/portal/patients/${patient.id}`}
            className="text-brand-600 block text-center text-[11px] font-semibold hover:underline"
          >
            View full history
          </Link>
        </div>
      )}

      {tab === "Reports" && (
        <div className="space-y-space-2">
          {loading ? (
            <p className="text-ink-400 text-[12px]">Loading…</p>
          ) : (summary?.documents.length ?? 0) === 0 ? (
            <p className="py-space-3 text-ink-400 text-center text-[12.5px]">
              No documents uploaded yet.
            </p>
          ) : (
            summary!.documents.map((d) => (
              <div
                key={d.id}
                className="border-line p-space-2 flex items-center justify-between rounded-md border"
              >
                <div className="gap-space-2 flex min-w-0 items-center">
                  <FileText size={14} className="text-ink-400 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-ink-900 truncate text-[12.5px] font-semibold">
                      {d.file_name}
                    </p>
                    <p className="text-ink-400 text-[11px]">
                      {DOCUMENT_TYPE_LABELS[d.document_type] || d.document_type} ·{" "}
                      {formatDate(d.uploaded_at)}
                    </p>
                  </div>
                </div>
                {d.sent_to_whatsapp_at && <Send size={13} className="text-success shrink-0" />}
              </div>
            ))
          )}
          <Link
            href={`/portal/patients/${patient.id}`}
            className="text-brand-600 block text-center text-[11px] font-semibold hover:underline"
          >
            Upload or send reports on the full record
          </Link>
        </div>
      )}
    </Card>
  );
}
