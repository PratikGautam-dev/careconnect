"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Building2, MoreVertical } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

export type SubscriptionRow = {
  id: number;
  hospitalName: string;
  plan: string;
  billingCycle: string;
  startDate: string;
  renewalDate: string;
  paymentStatus: "Paid" | "Pending" | "Failed";
  seats: number;
  status: "Active" | "Trial" | "Renewal Due" | "Expired" | "Cancelled";
};

const PAYMENT_TONE: Record<SubscriptionRow["paymentStatus"], "success" | "clay" | "neutral"> = {
  Paid: "success",
  Pending: "clay",
  Failed: "clay",
};

const STATUS_TONE: Record<SubscriptionRow["status"], "success" | "clay" | "neutral" | "brand"> = {
  Active: "success",
  Trial: "brand",
  "Renewal Due": "clay",
  Expired: "clay",
  Cancelled: "neutral",
};

type CreateSubscriptionColumnsOptions = {
  selectedIds: Set<number>;
  onToggle: (id: number) => void;
  onToggleAll: (checked: boolean) => void;
  allSelected: boolean;
};

/** Column defs for the Subscriptions "Hospital Subscriptions" table -- every
 * row here is fabricated (there's no plan/billing model in the backend yet,
 * see this page's own docstring), so unlike the other admin DataTable
 * columns files this one isn't reading from a real hook at all. Kept as its
 * own file/DataTable instance anyway so swapping in the real subscriptions
 * API later is a one-file change, not a table rewrite. */
export function createSubscriptionColumns({
  selectedIds,
  onToggle,
  onToggleAll,
  allSelected,
}: CreateSubscriptionColumnsOptions): ColumnDef<SubscriptionRow>[] {
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
          checked={selectedIds.has(row.original.id)}
          onChange={(e) => {
            e.stopPropagation();
            onToggle(row.original.id);
          }}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${row.original.hospitalName}`}
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
          <span className="text-ink-900 font-semibold">{row.original.hospitalName}</span>
        </div>
      ),
    },
    {
      id: "plan",
      header: "Plan",
      cell: ({ row }) => <span className="text-ink-600">{row.original.plan}</span>,
    },
    {
      id: "billingCycle",
      header: "Billing Cycle",
      cell: ({ row }) => <span className="text-ink-600">{row.original.billingCycle}</span>,
    },
    {
      id: "startDate",
      header: "Start Date",
      cell: ({ row }) => <span className="text-ink-600 whitespace-nowrap">{row.original.startDate}</span>,
    },
    {
      id: "renewalDate",
      header: "Renewal Date",
      cell: ({ row }) => <span className="text-ink-600 whitespace-nowrap">{row.original.renewalDate}</span>,
    },
    {
      id: "paymentStatus",
      header: "Payment Status",
      cell: ({ row }) => <Badge tone={PAYMENT_TONE[row.original.paymentStatus]}>{row.original.paymentStatus}</Badge>,
    },
    {
      id: "seats",
      header: "Seats",
      cell: ({ row }) => <span className="text-ink-600">{row.original.seats}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <Badge tone={STATUS_TONE[row.original.status]}>{row.original.status}</Badge>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: () => (
        <button
          type="button"
          onClick={(e) => e.stopPropagation()}
          aria-label="More actions"
          className="text-ink-400 hover:bg-paper flex h-7 w-7 items-center justify-center rounded-md hover:text-ink-700"
        >
          <MoreVertical size={15} />
        </button>
      ),
    },
  ];
}
