import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";

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
};

// Item 9 (Spec.md Section 0): kept identical to the full Appointments
// page's own STATUS_STYLES/LABELS -- both were drifting out of sync
// (missing attended/no_show here) before this alignment pass.
const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};

const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed",
  cancelled: "Cancelled",
  rescheduled: "Rescheduled",
  attended: "Attended",
  no_show: "No-show",
};

const SOURCE_LABELS: Record<string, string> = { whatsapp: "WhatsApp", staff: "Walk-in" };

const columns: ColumnDef<Appointment>[] = [
  {
    id: "scheduled_at",
    header: "Time",
    cell: ({ row }) => (
      <span className="whitespace-nowrap tabular-nums text-ink-600">{formatShortDateTime(row.original.scheduled_at)}</span>
    ),
  },
  {
    id: "reference_id",
    header: "Reference",
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-[12px] text-ink-400">{row.original.reference_id || "—"}</span>
    ),
  },
  {
    id: "patient",
    header: "Patient",
    cell: ({ row }) => {
      const a = row.original;
      return (
        <div className="text-ink-900">
          <div>
            <span className="font-semibold">{a.patient_name || a.phone}</span>
            {a.patient_name && <span className="ml-space-2 text-[12px] text-ink-400">{a.phone}</span>}
          </div>
          {a.patient_display_id && <div className="font-mono text-[11px] text-ink-400">{a.patient_display_id}</div>}
        </div>
      );
    },
  },
  {
    id: "doctor_name",
    header: "Doctor",
    cell: ({ row }) => <span className="text-ink-600">{row.original.doctor_name}</span>,
  },
  {
    id: "department_name",
    header: "Department",
    cell: ({ row }) => <span className="text-ink-600">{row.original.department_name}</span>,
  },
  {
    id: "source",
    header: "Source",
    cell: ({ row }) => <span className="text-ink-600">{SOURCE_LABELS[row.original.source] || row.original.source}</span>,
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => (
      <span
        className={cn(
          "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
          STATUS_STYLES[row.original.status] || "bg-black/4 text-ink-600",
        )}
      >
        {STATUS_LABELS[row.original.status] || row.original.status}
      </span>
    ),
  },
];

export function RecentAppointmentsTable({ appointments }: { appointments: Appointment[] }) {
  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">Recent appointments</h3>
        <Link href="/portal/patients" className="text-[12.5px] font-semibold text-brand-600 hover:underline">
          View all patients →
        </Link>
      </div>
      {appointments.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No appointments yet.</p>
      ) : (
        <DataTable columns={columns} data={appointments} getRowId={(a) => String(a.id)} />
      )}
    </Card>
  );
}
