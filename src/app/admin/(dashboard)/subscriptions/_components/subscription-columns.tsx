"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Building2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { SubscriptionRecord } from "@/hooks/useAdminSubscriptions";
import { SubscriptionCellAction } from "./subscriptions-cellaction";

const PAYMENT_LABEL: Record<string, string> = {
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
};
const PAYMENT_TONE: Record<string, "success" | "clay" | "neutral"> = {
  paid: "success",
  pending: "clay",
  failed: "clay",
};

// Exported -- the Tenants page's Hospital Profile detail panel (HospitalDetailPanel.tsx)
// reuses these same labels/tones for its own subscription-status badge rather than
// hardcoding a second copy.
export const STATUS_LABEL: Record<string, string> = {
  unassigned: "Unassigned",
  trial: "Trial",
  authorization_pending: "Awaiting Payment Setup",
  active: "Active",
  renewal_due: "Renewal Due",
  expired: "Expired",
  cancelled: "Cancelled",
};
export const STATUS_TONE: Record<string, "success" | "clay" | "neutral" | "brand"> = {
  unassigned: "neutral",
  trial: "brand",
  authorization_pending: "clay",
  active: "success",
  renewal_due: "clay",
  expired: "clay",
  cancelled: "neutral",
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

type CreateSubscriptionColumnsOptions = {
  onEdit: (row: SubscriptionRecord) => void;
  onExtendTrial: (row: SubscriptionRecord) => void;
  onCancelSubscription: (row: SubscriptionRecord) => void;
  onUnassign: (row: SubscriptionRecord) => void;
  onCancelBilling: (row: SubscriptionRecord) => void;
};

/** Column defs for the Subscriptions "Hospital Subscriptions" table --
 * backed by admin/subscriptions_api.py's real hospital<->plan assignment
 * (useAdminSubscriptions), one row per hospital regardless of whether it
 * has been assigned a plan yet. */
export function createSubscriptionColumns({
  onEdit,
  onExtendTrial,
  onCancelSubscription,
  onUnassign,
  onCancelBilling,
}: CreateSubscriptionColumnsOptions): ColumnDef<SubscriptionRecord>[] {
  return [
    {
      id: "hospitalName",
      header: "Hospital Name",
      cell: ({ row }) => (
        <div className="gap-space-2 flex items-center">
          <Building2 size={15} className="text-brand-600 shrink-0" />
          <span className="text-ink-900 font-semibold">{row.original.hospital_name}</span>
        </div>
      ),
    },
    {
      id: "plan",
      header: "Plan",
      cell: ({ row }) => <span className="text-ink-600">{row.original.plan_name ?? "—"}</span>,
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
      id: "paymentStatus",
      header: "Payment Status",
      cell: ({ row }) =>
        row.original.payment_status ? (
          <Badge tone={PAYMENT_TONE[row.original.payment_status]}>
            {PAYMENT_LABEL[row.original.payment_status]}
          </Badge>
        ) : (
          <span className="text-ink-400">—</span>
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
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <SubscriptionCellAction
          row={row.original}
          onEdit={onEdit}
          onExtendTrial={onExtendTrial}
          onCancelSubscription={onCancelSubscription}
          onUnassign={onUnassign}
          onCancelBilling={onCancelBilling}
        />
      ),
    },
  ];
}
