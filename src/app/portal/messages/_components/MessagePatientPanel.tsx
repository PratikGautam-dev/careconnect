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
export function MessagePatientPanel({
  patient,
  loading,
  onBookAppointment,
  onOrderTest,
  onBookDaycare,
}: Props) {
  if (loading) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">Looking up patient…</p>
      </Card>
    );
  }

  if (!patient) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          No patient record found for this number yet.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-space-4">
      <Card className="p-space-4">
        <div className="mb-space-3 gap-space-2 flex items-start justify-between">
          <p className="text-label text-ink-900 font-bold">Patient Details</p>
          <Badge tone="brand">Patient</Badge>
        </div>

        <div className="mb-space-3 gap-space-3 flex items-center">
          <span
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-[16px] font-bold",
              AVATAR_TINTS[patient.id % AVATAR_TINTS.length],
            )}
          >
            {initials(patient.name)}
          </span>
          <div className="min-w-0">
            <p className="text-ink-900 truncate text-[15px] font-bold">{patient.name || "—"}</p>
            <p className="text-ink-400 truncate text-[12px]">
              {patient.patient_display_id || `#${patient.id}`}
            </p>
          </div>
        </div>

        <div className="space-y-space-2 border-line pt-space-3 border-t text-[13px]">
          {(patient.age != null || patient.gender) && (
            <p className="gap-space-2 text-ink-600 flex items-center">
              <UserRound size={14} className="text-ink-400 shrink-0" />
              {patient.age != null ? `${patient.age} years` : ""}
              {patient.age != null && patient.gender ? ", " : ""}
              {patient.gender || ""}
            </p>
          )}
          <p className="gap-space-2 text-ink-600 flex items-center">
            <Phone size={14} className="text-ink-400 shrink-0" /> {patient.phone}
          </p>
          <p className="gap-space-2 text-ink-600 flex items-center">
            <Mail size={14} className="text-ink-400 shrink-0" /> —
          </p>
          <p className="gap-space-2 text-ink-600 flex items-center">
            <MapPin size={14} className="text-ink-400 shrink-0" /> —
          </p>
        </div>

        <div className="mt-space-3 gap-space-2 grid grid-cols-2">
          <Link
            href={`/portal/patients/${patient.id}`}
            className="border-line text-ink-900 flex h-9 items-center justify-center rounded-md border text-[12px] font-semibold hover:bg-black/[0.03]"
          >
            View Patient Profile
          </Link>
          <Link
            href={`/portal/patients/${patient.id}`}
            className="border-line text-ink-900 flex h-9 items-center justify-center rounded-md border text-[12px] font-semibold hover:bg-black/[0.03]"
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
          {
            label: "Share Report",
            icon: Send,
            disabled: true,
            title: "Coming soon — no report-sharing integration exists yet",
          },
        ]}
      />
    </div>
  );
}
