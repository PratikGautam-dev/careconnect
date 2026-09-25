"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Building2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { SubscriptionRecord } from "@/hooks/useAdminSubscriptions";

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

// Mirrors admin/subscriptions_api.py's _NON_TERMINAL_STATUSES exactly --
// razorpay_subscription_id stays set on a row forever as history even
// after the real subscription is cancelled (webhook/razorpay_subscription_
// routes.py never clears it), so "is there a live billed subscription to
// cancel" is id-set AND status still non-terminal, not id-set alone. Using
// id-set alone kept showing "Cancel Billing" on an already-cancelled row
// forever, with no way back to Assign/Edit.
const LIVE_BILLING_STATUSES = new Set(["authorization_pending", "active", "renewal_due"]);

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

type CreateSubscriptionColumnsOptions = {
  selectedIds: Set<number>;
  onToggle: (id: number) => void;
  onToggleAll: (checked: boolean) => void;
  allSelected: boolean;
  onEdit: (row: SubscriptionRecord) => void;
  onUnassign: (row: SubscriptionRecord) => void;
  onCancelBilling: (row: SubscriptionRecord) => void;
};

/** Column defs for the Subscriptions "Hospital Subscriptions" table --
 * backed by admin/subscriptions_api.py's real hospital<->plan assignment
 * (useAdminSubscriptions), one row per hospital regardless of whether it
 * has been assigned a plan yet. */
export function createSubscriptionColumns({
  selectedIds,
  onToggle,
  onToggleAll,
  allSelected,
  onEdit,
  onUnassign,
  onCancelBilling,
}: CreateSubscriptionColumnsOptions): ColumnDef<SubscriptionRecord>[] {
  return [
    {
      id: "select",
      header: () => (
        <input
          type="checkbox"
          checked={allSelected}
          onChange={(e) => onToggleAll(e.target.checked)}
          aria-label="Select all"
          className="accent-brand-600 h-4 w-4"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedIds.has(row.original.hospital_id)}
          onChange={(e) => {
            e.stopPropagation();
            onToggle(row.original.hospital_id);
          }}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${row.original.hospital_name}`}
          className="accent-brand-600 h-4 w-4"
        />
      ),
    },
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
      cell: ({ row }) => {
        // Real Razorpay billing owns status/payment_status while live (this
        // hospital set it up themselves via Settings -> Billing) -- the
        // manual assign/edit form would just get a 409 from the backend,
        // so it's not offered here; Cancel Billing is the only action.
        // Once cancelled/expired, the backend allows manual edits again
        // (the id sticks around as history, not a live-billing marker).
        if (
          row.original.razorpay_subscription_id &&
          LIVE_BILLING_STATUSES.has(row.original.status)
        ) {
          return (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onCancelBilling(row.original);
              }}
              className="text-ink-400 px-space-2 hover:bg-paper hover:text-error rounded-md py-1 text-[12px] font-semibold"
            >
              Cancel Billing
            </button>
          );
        }
        return (
          <div className="gap-space-1 flex items-center">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onEdit(row.original);
              }}
              className="text-brand-600 px-space-2 hover:bg-paper rounded-md py-1 text-[12px] font-semibold"
            >
              {row.original.status === "unassigned" ? "Assign" : "Edit"}
            </button>
            {row.original.status !== "unassigned" && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onUnassign(row.original);
                }}
                className="text-ink-400 px-space-2 hover:bg-paper hover:text-error rounded-md py-1 text-[12px] font-semibold"
              >
                Unassign
              </button>
            )}
          </div>
        );
      },
    },
  ];
}
