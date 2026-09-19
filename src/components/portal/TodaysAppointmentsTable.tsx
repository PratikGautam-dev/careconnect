import type { ColumnDef } from "@tanstack/react-table";
import { CalendarCheck } from "lucide-react";
import Link from "next/link";
import {
  AVATAR_TINTS,
  STATUS_LABELS,
  STATUS_STYLES,
  TYPE_ICONS,
  initials,
} from "@/app/portal/appointments/_components/appointments-columns";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import { TYPE_LABELS } from "@/hooks/useAppointments";

type Appointment = {
  id: number;
  phone: string;
  patient_name: string | null;
  patient_display_id: string | null;
  department_name: string;
  doctor_name: string;
  scheduled_at: string;
  status: string;
  source: string;
  reference_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
};

// Same columns/styling as the Doctor appointments table (appointments-
// columns.tsx), minus select/Actions -- managing a booking happens on the
// full page this links to, not from a dashboard preview row.
const columns: ColumnDef<Appointment>[] = [
  {
    id: "reference_id",
    header: "Appointment ID",
    cell: ({ row }) => (
      <span className="text-ink-600 font-mono text-[12px] whitespace-nowrap">
        {row.original.reference_id || "—"}
      </span>
    ),
  },
  {
    id: "scheduled_at",
    header: "Time",
    cell: ({ row }) => (
      <span className="text-ink-600 whitespace-nowrap tabular-nums">
        {formatShortDateTime(row.original.scheduled_at)}
      </span>
    ),
  },
  {
    id: "patient",
    header: "Patient",
    cell: ({ row }) => {
      const a = row.original;
      return (
        <div className="gap-space-2 flex items-center">
          <span
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
              AVATAR_TINTS[a.id % AVATAR_TINTS.length],
            )}
          >
            {initials(a.patient_name, a.phone)}
          </span>
          <div className="min-w-0">
            <p className="text-ink-900 truncate font-semibold">{a.patient_name || a.phone}</p>
            {a.patient_name && <p className="text-ink-400 truncate text-[11.5px]">{a.phone}</p>}
          </div>
        </div>
      );
    },
  },
  {
    id: "doctor_name",
    header: "Doctor",
    cell: ({ row }) => <span className="text-ink-600">{row.original.doctor_name || "—"}</span>,
  },
  {
    id: "department_name",
    header: "Department",
    cell: ({ row }) => <span className="text-ink-600">{row.original.department_name || "—"}</span>,
  },
  {
    id: "type",
    header: "Appointment type",
    cell: ({ row }) => {
      const a = row.original;
      const Icon = (a.appointment_type_id && TYPE_ICONS[a.appointment_type_id]) || CalendarCheck;
      return (
        <span className="gap-space-2 text-ink-600 inline-flex items-center">
          <Icon size={14} strokeWidth={2} className="text-ink-400 shrink-0" />
          {a.appointment_type_id
            ? TYPE_LABELS[a.appointment_type_id] || a.appointment_type_id
            : "Consultation"}
        </span>
      );
    },
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => (
      <span
        className={cn(
          "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
          STATUS_STYLES[row.original.status] || "text-ink-600 bg-black/4",
        )}
      >
        {STATUS_LABELS[row.original.status] || row.original.status}
      </span>
    ),
  },
  {
    id: "mode",
    header: "Mode",
    cell: ({ row }) => {
      const a = row.original;
      if (a.appointment_type_id === "tele") {
        return a.video_link ? (
          <a
            href={a.video_link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-600 text-[12.5px] font-semibold hover:underline"
          >
            Video · Join
          </a>
        ) : (
          <span className="text-ink-600 text-[12.5px]">Video</span>
        );
      }
      return <span className="text-ink-600 text-[12.5px]">In-person</span>;
    },
  },
];

export function TodaysAppointmentsTable({ appointments }: { appointments: Appointment[] }) {
  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Today&apos;s appointments</h3>
        <Link
          href="/portal/appointments"
          className="text-brand-600 text-[12.5px] font-semibold hover:underline"
        >
          View all appointments →
        </Link>
      </div>
      {appointments.length === 0 ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">No appointments today.</p>
      ) : (
        <DataTable columns={columns} data={appointments} getRowId={(a) => String(a.id)} />
      )}
    </Card>
  );
}
