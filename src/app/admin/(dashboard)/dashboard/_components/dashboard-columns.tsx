"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import type { BillingRecord } from "@/hooks/useAdminBillingRecords";
import type { RecentActivity } from "@/hooks/useSuperAdminDashboard";
import type { SubscriptionRecord } from "@/hooks/useAdminSubscriptions";

// Same status vocabulary as subscription-columns.tsx (admin/subscriptions)
// -- duplicated rather than imported since that file's copy is a local
// const, not exported, and this dashboard's read-only preview table has no
// need for the full column set (actions, checkboxes) that file also owns.
export const SUBSCRIPTION_STATUS_LABEL: Record<string, string> = {
  unassigned: "Unassigned",
  trial: "Trial",
  authorization_pending: "Awaiting Payment Setup",
  active: "Active",
  renewal_due: "Renewal Due",
  expired: "Expired",
  cancelled: "Cancelled",
};
export const SUBSCRIPTION_STATUS_TONE: Record<string, "success" | "clay" | "neutral" | "brand"> = {
  unassigned: "neutral",
  trial: "brand",
  authorization_pending: "clay",
  active: "success",
  renewal_due: "clay",
  expired: "clay",
  cancelled: "neutral",
};

function daysUntil(iso: string): number {
  const ms = new Date(`${iso}T00:00:00`).getTime() - new Date(new Date().toDateString()).getTime();
  return Math.round(ms / 86_400_000);
}

/** "Recent Renewals" preview -- real subscriptions with a renewal_date,
 * soonest first (useAdminSubscriptions / db.list_subscriptions()). */
export const renewalColumns: ColumnDef<SubscriptionRecord, unknown>[] = [
  {
    id: "hospital",
    header: "Hospital",
    cell: ({ row }) => (
      <span className="text-ink-900 font-semibold">{row.original.hospital_name}</span>
    ),
  },
  {
    id: "plan",
    header: "Plan",
    cell: ({ row }) => <span className="text-ink-600">{row.original.plan_name ?? "—"}</span>,
  },
  {
    id: "renewalDate",
    header: "Renewal Date",
    cell: ({ row }) => (
      <span className="text-ink-600 whitespace-nowrap">
        {formatDate(row.original.renewal_date)}
      </span>
    ),
  },
  {
    id: "daysLeft",
    header: "Days Left",
    cell: ({ row }) => {
      const d = row.original.renewal_date ? daysUntil(row.original.renewal_date) : null;
      if (d === null) return <span className="text-ink-400">—</span>;
      return <span className={d <= 7 ? "text-clay-700 font-semibold" : "text-ink-600"}>{d}</span>;
    },
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge tone={SUBSCRIPTION_STATUS_TONE[row.original.status]}>
        {SUBSCRIPTION_STATUS_LABEL[row.original.status]}
      </Badge>
    ),
  },
];

/** "Recent Billing Records" preview -- real payments ledger rows
 * (useAdminBillingRecords / admin/subscriptions_api.py's list_billing_records). */
export const billingRecordColumns: ColumnDef<BillingRecord, unknown>[] = [
  {
    id: "hospital",
    header: "Hospital",
    cell: ({ row }) => (
      <span className="text-ink-900 font-semibold">{row.original.hospital_name}</span>
    ),
  },
  {
    id: "plan",
    header: "Plan",
    cell: ({ row }) => (
      <span className="text-ink-600">
        {row.original.plan_name ?? "—"}
        {row.original.billing_cycle ? ` · ${row.original.billing_cycle}` : ""}
      </span>
    ),
  },
  {
    id: "amount",
    header: "Amount",
    cell: ({ row }) => (
      <span className="text-ink-900 font-semibold">
        ₹{row.original.amount.toLocaleString("en-IN")}
      </span>
    ),
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge tone={row.original.status === "paid" ? "success" : "clay"}>
        {row.original.status === "paid"
          ? "Paid"
          : row.original.status === "pending"
            ? "Pending"
            : "Failed"}
      </Badge>
    ),
  },
  {
    id: "createdAt",
    header: "Date",
    cell: ({ row }) => (
      <span className="text-ink-600 whitespace-nowrap">
        {formatDate(row.original.paid_at ?? row.original.created_at)}
      </span>
    ),
  },
];

/** "Latest Activity Log" -- real, cross-tenant audit log
 * (useSuperAdminDashboard / db.get_audit_logs()). */
export const activityColumns: ColumnDef<RecentActivity, unknown>[] = [
  {
    id: "time",
    header: "Time",
    cell: ({ row }) => (
      <span className="text-ink-600 whitespace-nowrap">
        {formatShortDateTime(row.original.created_at)}
      </span>
    ),
  },
  {
    id: "action",
    header: "Action",
    cell: ({ row }) => (
      <span className="px-space-2 bg-brand-50 text-brand-700 inline-block rounded-full py-0.5 text-[11px] font-semibold">
        {row.original.action}
      </span>
    ),
  },
  {
    id: "details",
    header: "Details",
    cell: ({ row }) => <span className="text-ink-600">{row.original.hospital_name || "—"}</span>,
  },
  {
    id: "by",
    header: "By",
    cell: ({ row }) => <span className="text-ink-600">{row.original.actor_label}</span>,
  },
];

export type MockTicket = {
  id: string;
  hospital: string;
  subject: string;
  priority: "High" | "Medium" | "Low";
  status: "Open" | "In Progress" | "Resolved";
};

const TICKET_PRIORITY_TONE: Record<MockTicket["priority"], "clay" | "neutral"> = {
  High: "clay",
  Medium: "clay",
  Low: "neutral",
};
const TICKET_STATUS_TONE: Record<MockTicket["status"], "clay" | "brand" | "success"> = {
  Open: "clay",
  "In Progress": "brand",
  Resolved: "success",
};

// Only table on this page still backed by mock data -- no support-ticket
// model exists in this codebase yet (confirmed against the backend); every
// other table/tile here is real.
export const ticketColumns: ColumnDef<MockTicket, unknown>[] = [
  {
    id: "id",
    header: "#",
    cell: ({ row }) => <span className="text-ink-600">{row.original.id}</span>,
  },
  {
    id: "hospital",
    header: "Hospital",
    cell: ({ row }) => (
      <span className="text-ink-900 font-semibold">{row.original.hospital}</span>
    ),
  },
  {
    id: "subject",
    header: "Subject",
    cell: ({ row }) => <span className="text-ink-600">{row.original.subject}</span>,
  },
  {
    id: "priority",
    header: "Priority",
    cell: ({ row }) => (
      <Badge tone={TICKET_PRIORITY_TONE[row.original.priority]}>{row.original.priority}</Badge>
    ),
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge tone={TICKET_STATUS_TONE[row.original.status]}>{row.original.status}</Badge>
    ),
  },
];
