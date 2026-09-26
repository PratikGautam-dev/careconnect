"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/formatDate";
import type { SubscriptionRecord } from "@/hooks/useAdminSubscriptions";

// Same status vocabulary as /admin/subscriptions' subscription-columns.tsx
// and the dashboard's dashboard-columns.tsx -- duplicated locally rather
// than imported, matching how those two files already each keep their own
// copy (neither exports it).
const STATUS_LABEL: Record<string, string> = {
  unassigned: "Unassigned",
  trial: "Trial",
  authorization_pending: "Awaiting Payment Setup",
  active: "Active",
  renewal_due: "Renewal Due",
  expired: "Expired",
  cancelled: "Cancelled",
};
const STATUS_TONE: Record<string, "success" | "clay" | "neutral" | "brand"> = {
  unassigned: "neutral",
  trial: "brand",
  authorization_pending: "clay",
  active: "success",
  renewal_due: "clay",
  expired: "clay",
  cancelled: "neutral",
};

/** Read-only subscription preview for a single tenant's own detail page --
 * unlike /admin/subscriptions' own columns (assign/edit/unassign/cancel
 * actions), this table has none: managing a subscription still only
 * happens on /admin/subscriptions. This is a summary, plus (once a hospital
 * can have more than one subscription row over time) a row to click to
 * scope the Billing History table below it. */
export function createTenantSubscriptionColumns(): ColumnDef<SubscriptionRecord>[] {
  return [
    {
      id: "plan",
      header: "Plan",
      cell: ({ row }) => (
        <span className="text-ink-900 font-semibold">{row.original.plan_name ?? "Unassigned"}</span>
      ),
    },
    {
      id: "billingCycle",
      header: "Billing Cycle",
      cell: ({ row }) => (
        <span className="text-ink-600 capitalize">{row.original.billing_cycle ?? "—"}</span>
      ),
    },
    {
      id: "startDate",
      header: "Start Date",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">
          {formatDate(row.original.start_date)}
        </span>
      ),
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
      id: "seats",
      header: "Seats",
      cell: ({ row }) => (
        <span className="text-ink-600">
          {row.original.seats_used}
          {row.original.max_users != null ? ` / ${row.original.max_users}` : ""}
        </span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={STATUS_TONE[row.original.status]}>{STATUS_LABEL[row.original.status]}</Badge>
      ),
    },
  ];
}
