"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import type { MySupportTicketRow, TicketPriority, TicketStatus } from "@/hooks/useSupportTickets";

// Same vocabulary as the admin Support Tickets table
// (admin/support-tickets/_components/support-ticket-columns.tsx) --
// duplicated rather than imported, same "local const, not a cross-app
// import" convention the dashboard's own columns file already follows.
const STATUS_LABELS: Record<TicketStatus, string> = {
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

const PRIORITY_LABELS: Record<TicketPriority, string> = {
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

export const myTicketColumns: ColumnDef<MySupportTicketRow>[] = [
  {
    id: "ticket_number",
    header: "Ticket #",
    cell: ({ row }) => (
      <span className="text-ink-900 font-semibold whitespace-nowrap">{row.original.ticket_number}</span>
    ),
  },
  {
    id: "subject",
    header: "Subject",
    cell: ({ row }) => <span className="text-ink-900">{row.original.subject}</span>,
  },
  {
    id: "category",
    header: "Category",
    cell: ({ row }) => (
      <span className="text-ink-600">{row.original.category_name || "Uncategorized"}</span>
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
