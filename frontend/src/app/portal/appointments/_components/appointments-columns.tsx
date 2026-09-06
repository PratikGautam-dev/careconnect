"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import { TYPE_LABELS, type Appointment } from "@/hooks/useAppointments";
import { AppointmentCellAction } from "./appointments-cellaction";

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};
export const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled",
  attended: "Attended", no_show: "No-show",
};
const SOURCE_LABELS: Record<string, string> = { whatsapp: "WhatsApp", staff: "Walk-in" };
// Lab Test Phase 2 follow-up's report lifecycle -- report_ready is never
// advanced from here (only automatically, by uploading a lab_report
// document against the appointment), so it has no "next" label.
const LAB_STATUS_LABELS: Record<string, string> = {
  booked: "Booked", sample_collected: "Sample Collected", processing: "Processing", report_ready: "Report Ready",
};
const LAB_STATUS_NEXT_LABEL: Record<string, string> = {
  booked: "Mark Sample Collected", sample_collected: "Mark Processing",
};

type CreateAppointmentColumnsOptions = {
  selected: Set<number>;
  toggleSelected: (id: number, checked: boolean) => void;
  toggleSelectAll: (checked: boolean) => void;
  allSelected: boolean;
  deletableCount: number;
  markingAttendanceId: number | null;
  onAttendance: (id: number, attended: boolean) => void;
  advancingLabStatusId: number | null;
  onAdvanceLabStatus: (id: number) => void;
  cancelPanelId: number | null;
  reschedulePanelId: number | null;
  onOpenReschedule: (id: number) => void;
  onOpenCancel: (id: number) => void;
  deletingId: number | null;
  onDelete: (id: number) => void;
};

/** Column definitions for the /portal/appointments DataTable -- same 13
 * columns (selection through trailing actions) the hand-rolled table used
 * to render directly, just expressed as ColumnDefs so DataTable (@tanstack/
 * react-table under the hood) owns rendering + client-side pagination. */
export function createAppointmentColumns({
  selected, toggleSelected, toggleSelectAll, allSelected, deletableCount,
  markingAttendanceId, onAttendance,
  advancingLabStatusId, onAdvanceLabStatus,
  cancelPanelId, reschedulePanelId, onOpenReschedule, onOpenCancel,
  deletingId, onDelete,
}: CreateAppointmentColumnsOptions): ColumnDef<Appointment>[] {
  return [
    {
      id: "select",
      header: () => (
        <PermissionGate page="appointments" action="delete">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={(e) => toggleSelectAll(e.target.checked)}
            disabled={deletableCount === 0}
            className="h-4 w-4 accent-brand-600"
            aria-label="Select all deletable appointments"
          />
        </PermissionGate>
      ),
      cell: ({ row }) => {
        const a = row.original;
        if (a.status === "booked") return null;
        return (
          <PermissionGate page="appointments" action="delete">
            <input
              type="checkbox"
              checked={selected.has(a.id)}
              onChange={(e) => toggleSelected(a.id, e.target.checked)}
              className="h-4 w-4 accent-brand-600"
              aria-label={`Select appointment ${a.reference_id || a.id}`}
            />
          </PermissionGate>
        );
      },
    },
    {
      id: "scheduled_at",
      header: "Appointment time",
      cell: ({ row }) => (
        <span className="whitespace-nowrap tabular-nums text-ink-600">{formatShortDateTime(row.original.scheduled_at)}</span>
      ),
    },
    {
      id: "created_at",
      header: "Booked",
      cell: ({ row }) => (
        <span className="whitespace-nowrap tabular-nums text-ink-400">
          {row.original.created_at ? formatShortDateTime(row.original.created_at) : "—"}
        </span>
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
            <div>{a.phone}</div>
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
      id: "type",
      header: "Type",
      cell: ({ row }) => {
        const a = row.original;
        return (
          <div className="text-ink-600">
            <div>{a.appointment_type_id ? TYPE_LABELS[a.appointment_type_id] || a.appointment_type_id : "—"}</div>
            {/* Tele-consultation Phase 2 (confirmed with the user directly):
                staff need the video link too, not just the doctor's own
                "Today's appointments" widget -- withheld from the patient's
                immediate confirmation, but always visible here. */}
            {a.appointment_type_id === "tele" && a.video_link && (
              <a
                href={a.video_link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11.5px] font-semibold text-brand-600 hover:underline"
              >
                🎥 Join
              </a>
            )}
          </div>
        );
      },
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
            STATUS_STYLES[row.original.status] || "bg-black/[0.04] text-ink-600",
          )}
        >
          {STATUS_LABELS[row.original.status] || row.original.status}
        </span>
      ),
    },
    {
      id: "visited",
      header: "Visited",
      cell: ({ row }) => {
        const a = row.original;
        if (a.status !== "booked" && a.status !== "attended" && a.status !== "no_show") {
          return <span className="text-[12.5px] text-ink-300">—</span>;
        }
        // Admin-editable at any time, not gated on the scheduled time having
        // passed, and freely re-toggleable (not a one-way door) -- per direct
        // portal feedback.
        return (
          <span className="inline-flex items-center gap-space-2 whitespace-nowrap">
            <button
              type="button"
              onClick={() => onAttendance(a.id, true)}
              disabled={markingAttendanceId === a.id}
              className={cn(
                "text-[12.5px] font-semibold disabled:opacity-50",
                a.status === "attended" ? "text-success underline" : "text-ink-400 hover:text-success hover:underline",
              )}
            >
              Yes
            </button>
            <span className="text-ink-300">/</span>
            <button
              type="button"
              onClick={() => onAttendance(a.id, false)}
              disabled={markingAttendanceId === a.id}
              className={cn(
                "text-[12.5px] font-semibold disabled:opacity-50",
                a.status === "no_show" ? "text-error underline" : "text-ink-400 hover:text-error hover:underline",
              )}
            >
              No
            </button>
          </span>
        );
      },
    },
    {
      id: "lab_status",
      header: "Lab Status",
      cell: ({ row }) => {
        const a = row.original;
        if (!a.lab_status) return <span className="text-[12.5px] text-ink-300">—</span>;
        return (
          <span className="inline-flex items-center gap-space-2 whitespace-nowrap">
            <span
              className={cn(
                "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                a.lab_status === "report_ready" ? "bg-success-tint text-success" : "bg-black/[0.04] text-ink-600",
              )}
            >
              {LAB_STATUS_LABELS[a.lab_status] || a.lab_status}
            </span>
            {LAB_STATUS_NEXT_LABEL[a.lab_status] && (
              <button
                type="button"
                onClick={() => onAdvanceLabStatus(a.id)}
                disabled={advancingLabStatusId === a.id}
                className="text-[12px] font-semibold text-brand-600 hover:underline disabled:opacity-50"
              >
                {LAB_STATUS_NEXT_LABEL[a.lab_status]}
              </button>
            )}
          </span>
        );
      },
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="text-right">
          <AppointmentCellAction
            appointment={row.original}
            cancelPanelId={cancelPanelId}
            reschedulePanelId={reschedulePanelId}
            onOpenReschedule={onOpenReschedule}
            onOpenCancel={onOpenCancel}
            deletingId={deletingId}
            onDelete={onDelete}
          />
        </div>
      ),
    },
  ];
}
