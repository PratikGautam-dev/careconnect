"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { ChevronDown, ChevronUp } from "lucide-react";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { cn } from "@/lib/cn";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import type { Note, Visit } from "@/hooks/usePatientDetail";

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

type CreateVisitHistoryColumnsOptions = {
  followupPanelId: number | null;
  onOpenFollowup: (v: Visit) => void;
  onCloseFollowup: () => void;
  expandedVisit: number | null;
  setExpandedVisit: (id: number | null) => void;
  notesByVisit: (visitId: number) => Note[];
};

/** Column definitions for the patient detail page's visit-history DataTable
 * -- same 10 columns the hand-rolled table used to render directly. Follow-
 * up and Notes stay as their own columns (not combined into one actions
 * menu) since both show real at-a-glance info -- valid-until date, note
 * count -- alongside their toggle, not just a bare action. */
export function createVisitHistoryColumns({
  followupPanelId, onOpenFollowup, onCloseFollowup,
  expandedVisit, setExpandedVisit, notesByVisit,
}: CreateVisitHistoryColumnsOptions): ColumnDef<Visit>[] {
  return [
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
        const v = row.original;
        return (
          <div className="text-ink-600">
            <div>{v.appointment_type_id ? TYPE_LABELS[v.appointment_type_id] || v.appointment_type_id : "—"}</div>
            {v.appointment_type_id === "tele" && v.video_link && (
              <a
                href={v.video_link}
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
      id: "followup",
      header: "Follow-up",
      cell: ({ row }) => {
        const v = row.original;
        if (v.status !== "attended") return <span className="text-ink-300">—</span>;
        return (
          <div className="flex items-center gap-space-2 whitespace-nowrap">
            <span
              className={cn(
                "text-[12px] font-semibold",
                v.followup_valid_until && new Date(v.followup_valid_until) < new Date() ? "text-error" : "text-ink-600",
              )}
            >
              {v.followup_valid_until ? `Until ${formatDate(v.followup_valid_until)}` : "—"}
            </span>
            <PermissionGate page="appointments" action="write">
              <button
                type="button"
                onClick={() => (followupPanelId === v.id ? onCloseFollowup() : onOpenFollowup(v))}
                className="text-[11.5px] font-semibold text-brand-600 hover:underline"
              >
                {followupPanelId === v.id ? "Close" : "Follow-up…"}
              </button>
            </PermissionGate>
          </div>
        );
      },
    },
    {
      id: "notes",
      header: "",
      cell: ({ row }) => {
        const v = row.original;
        const expanded = expandedVisit === v.id;
        const visitNotes = notesByVisit(v.id);
        return (
          <div className="text-right">
            <button
              type="button"
              onClick={() => setExpandedVisit(expanded ? null : v.id)}
              className="inline-flex items-center gap-1 whitespace-nowrap text-[12px] font-semibold text-brand-600 hover:underline"
            >
              {visitNotes.length > 0 ? `${visitNotes.length} note${visitNotes.length > 1 ? "s" : ""}` : "Notes"}
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        );
      },
    },
  ];
}
