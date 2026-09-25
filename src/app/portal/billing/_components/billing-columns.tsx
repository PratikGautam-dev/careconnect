"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import type { PaymentRow } from "@/hooks/usePayments";
import { formatShortDateTime } from "@/lib/formatDate";

export const PAYMENT_STATUS_LABELS: Record<PaymentRow["status"], string> = {
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
  expired: "Expired",
  pay_at_hospital: "Pay at Hospital",
};

export const PAYMENT_STATUS_TONES: Record<PaymentRow["status"], "success" | "clay" | "neutral"> = {
  paid: "success",
  pending: "clay",
  pay_at_hospital: "clay",
  failed: "neutral",
  expired: "neutral",
};

export const PAYMENT_METHOD_LABELS: Record<PaymentRow["method"], string> = {
  online: "Online",
  pay_at_hospital: "Pay at Hospital",
};

type CreateBillingColumnsOptions = {
  onSelect: (row: PaymentRow) => void;
};

/** Column defs for the /portal/billing DataTable -- every column here is a
 * real payments/appointments field (see usePayments.ts's own docstring for
 * where each one comes from). */
export function createBillingColumns({
  onSelect,
}: CreateBillingColumnsOptions): ColumnDef<PaymentRow>[] {
  return [
    {
      id: "patient",
      header: "Patient",
      cell: ({ row }) => {
        const p = row.original;
        return (
          <button type="button" onClick={() => onSelect(p)} className="text-left">
            <span className="text-ink-900 truncate font-semibold">{p.patient_name || "—"}</span>
            {p.patient_phone && (
              <span className="text-ink-400 block text-[11.5px]">{p.patient_phone}</span>
            )}
          </button>
        );
      },
    },
    {
      id: "reference",
      header: "Reference",
      cell: ({ row }) => <span className="text-ink-600">{row.original.reference_id || "—"}</span>,
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
      id: "method",
      header: "Method",
      cell: ({ row }) => (
        <span className="text-ink-600">{PAYMENT_METHOD_LABELS[row.original.method]}</span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={PAYMENT_STATUS_TONES[row.original.status]}>
          {PAYMENT_STATUS_LABELS[row.original.status]}
        </Badge>
      ),
    },
    {
      id: "date",
      header: "Date",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">
          {formatShortDateTime(row.original.paid_at || row.original.created_at)}
        </span>
      ),
    },
  ];
}
