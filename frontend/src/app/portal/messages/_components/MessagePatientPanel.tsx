"use client";

import Link from "next/link";
import {
  BedDouble,
  CalendarPlus,
  FlaskConical,
  Mail,
  MapPin,
  Phone,
  Send,
  UserRound,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { QuickActions } from "@/components/portal/QuickActions";
import { cn } from "@/lib/cn";
import type { Patient } from "@/hooks/usePatients";
import { AVATAR_TINTS, initials } from "@/app/portal/patients/_components/patients-columns";

type Props = {
  patient: Patient | null;
  loading: boolean;
  onBookAppointment: () => void;
  onOrderTest: () => void;
  onBookDaycare: () => void;
};

/** Right-rail "Patient Details" panel for /portal/messages -- matches the
 * reference layout (minus Recent Files & Reports, dropped per the user's
 * own instruction). Every field shown is real (resolved by phone via
 * useMessages' matchedPatient, the same patients directory /portal/patients
 * itself reads) except Email, which this schema has no column for anywhere
 * -- shown as "—" rather than invented. Share Report/Send Email have no
 * backing integration yet, so they're disabled with a "Coming soon" title,
 * same convention as every other
 * not-yet-built action elsewhere in the portal (e.g. the Doctors page's
 * "Send message"). Book Appointment/Order Diagnostic Test/Book Daycare are
 * real -- they open the same dialogs the Appointments/Diagnostic/Daycare
 * pages use, pre-filled with this conversation's phone (and name, once
 * matched). */
export function MessagePatientPanel({ patient, loading, onBookAppointment, onOrderTest, onBookDaycare }: Props) {
  if (loading) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-center text-[13px] text-ink-400">Looking up patient…</p>
      </Card>
    );
  }

  if (!patient) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-center text-[13px] text-ink-400">
          No patient record found for this number yet.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-space-4">
      <Card className="p-space-4">
        <div className="mb-space-3 flex items-start justify-between gap-space-2">
          <p className="text-label font-bold text-ink-900">Patient Details</p>
          <Badge tone="brand">Patient</Badge>
        </div>

        <div className="mb-space-3 flex items-center gap-space-3">
          <span
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-[16px] font-bold",
              AVATAR_TINTS[patient.id % AVATAR_TINTS.length],
            )}
          >
            {initials(patient.name)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[15px] font-bold text-ink-900">{patient.name || "—"}</p>
            <p className="truncate text-[12px] text-ink-400">{patient.patient_display_id || `#${patient.id}`}</p>
          </div>
        </div>

        <div className="space-y-space-2 border-t border-line pt-space-3 text-[13px]">
          {(patient.age != null || patient.gender) && (
            <p className="flex items-center gap-space-2 text-ink-600">
              <UserRound size={14} className="shrink-0 text-ink-400" />
              {patient.age != null ? `${patient.age} years` : ""}
              {patient.age != null && patient.gender ? ", " : ""}
              {patient.gender || ""}
            </p>
          )}
          <p className="flex items-center gap-space-2 text-ink-600">
            <Phone size={14} className="shrink-0 text-ink-400" /> {patient.phone}
          </p>
          <p className="flex items-center gap-space-2 text-ink-600">
            <Mail size={14} className="shrink-0 text-ink-400" /> —
          </p>
          <p className="flex items-center gap-space-2 text-ink-600">
            <MapPin size={14} className="shrink-0 text-ink-400" /> —
          </p>
        </div>

        <div className="mt-space-3 grid grid-cols-2 gap-space-2">
          <Link
            href={`/portal/patients/${patient.id}`}
            className="flex h-9 items-center justify-center rounded-md border border-line text-[12px] font-semibold text-ink-900 hover:bg-black/[0.03]"
          >
            View Patient Profile
          </Link>
          <Link
            href={`/portal/patients/${patient.id}`}
            className="flex h-9 items-center justify-center rounded-md border border-line text-[12px] font-semibold text-ink-900 hover:bg-black/[0.03]"
          >
            View Medical History
          </Link>
        </div>
      </Card>

      <QuickActions
        columns={1}
        actions={[
          { label: "Book Appointment", icon: CalendarPlus, onClick: onBookAppointment },
          { label: "Order Diagnostic Test", icon: FlaskConical, onClick: onOrderTest },
          { label: "Book Daycare Appointment", icon: BedDouble, onClick: onBookDaycare },
          { label: "Share Report", icon: Send, disabled: true, title: "Coming soon — no report-sharing integration exists yet" },
        ]}
      />
    </div>
  );
}
