"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import type { BillingRecord } from "@/hooks/useAdminBillingRecords";

const STATUS_LABEL: Record<BillingRecord["status"], string> = {
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
};
const STATUS_TONE: Record<BillingRecord["status"], "success" | "clay" | "neutral"> = {
  paid: "success",
  pending: "clay",
  failed: "clay",
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Column defs for the Plans & Billing "Recent Billing Records" table --
 * real hospital->CareConnect subscription charge events (payments table,
 * payment_for='subscription'), one row per webhook-confirmed charge, via
 * useAdminBillingRecords. */
export function createBillingColumns(): ColumnDef<BillingRecord>[] {
  return [
    {
      id: "paymentId",
      header: "Payment ID",
      cell: ({ row }) => (
        <span className="text-brand-600 font-semibold">
          {row.original.razorpay_payment_id ?? `#${row.original.id}`}
        </span>
      ),
    },
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
          {row.original.billing_cycle ? ` (${row.original.billing_cycle})` : ""}
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
      id: "createdAt",
      header: "Charged On",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">
          {formatDateTime(row.original.created_at)}
        </span>
      ),
    },
    {
      id: "paidAt",
      header: "Paid At",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">
          {formatDateTime(row.original.paid_at)}
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
