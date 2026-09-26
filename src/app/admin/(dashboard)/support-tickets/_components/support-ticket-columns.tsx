"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import type { SupportTicketRow, TicketPriority, TicketStatus } from "@/hooks/useAdminSupportTickets";

export const STATUS_LABELS: Record<TicketStatus, string> = {
  open: "Open",
  in_process: "In Process",
  on_hold: "On Hold",
  completed: "Completed",
};
const STATUS_TINT: Record<TicketStatus, string> = {
  open: "bg-clay-100 text-clay-700",
  in_process: "bg-brand-50 text-brand-600",
  on_hold: "bg-error-tint text-error",
  completed: "bg-success-tint text-success",
};

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <span className={cn("px-space-2 rounded-full py-0.5 text-[11px] font-semibold", STATUS_TINT[status])}>
      {STATUS_LABELS[status]}
    </span>
  );
}

export const PRIORITY_LABELS: Record<TicketPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};
const PRIORITY_TINT: Record<TicketPriority, string> = {
  low: "text-ink-400",
  medium: "text-ink-600",
  high: "text-clay-700",
  urgent: "text-error",
};

export function PriorityLabel({ priority }: { priority: TicketPriority }) {
  return <span className={cn("font-semibold", PRIORITY_TINT[priority])}>{PRIORITY_LABELS[priority]}</span>;
}

type CreateColumnsOptions = {
  onSelect: (row: SupportTicketRow) => void;
};

export function createSupportTicketColumns({
  onSelect,
}: CreateColumnsOptions): ColumnDef<SupportTicketRow>[] {
  return [
    {
      id: "ticket_number",
      header: "Ticket #",
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => onSelect(row.original)}
          className="text-ink-900 text-left font-semibold whitespace-nowrap"
        >
          {row.original.ticket_number}
        </button>
      ),
    },
    {
      id: "subject",
      header: "Subject",
      cell: ({ row }) => {
        const t = row.original;
        return (
          <button type="button" onClick={() => onSelect(t)} className="text-left">
            <p className="text-ink-900">{t.subject}</p>
          </button>
        );
      },
    },
    {
      id: "category",
      header: "Category",
      cell: ({ row }) => (
        <span className="text-ink-600">{row.original.category_name || "Uncategorized"}</span>
      ),
    },
    {
      id: "hospital",
      header: "Hospital",
      cell: ({ row }) => <span className="text-ink-600">{row.original.hospital_name}</span>,
    },
    {
      id: "submitted_by",
      header: "Submitted By",
      cell: ({ row }) => (
        <span className="text-ink-600">
          {row.original.submitted_by_name || row.original.submitted_by_email}
        </span>
      ),
    },
    {
      id: "priority",
      header: "Priority",
      cell: ({ row }) => <PriorityLabel priority={row.original.priority} />,
    },
    {
      id: "created_at",
      header: "Submitted",
      cell: ({ row }) => <span className="text-ink-600">{formatDate(row.original.created_at)}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
  ];
}
