"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import type { BillingRow } from "@/hooks/useBillingOverview";

export const BILL_TYPE_LABELS: Record<BillingRow["bill_type"], string> = {
  appointment: "Appointment", pharmacy: "Pharmacy",
};
export const BILL_TYPE_TONES: Record<BillingRow["bill_type"], "brand" | "clay"> = {
  appointment: "brand", pharmacy: "clay",
};

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  paid: "Paid", pending: "Unpaid", partially_paid: "Partially Paid", failed: "Failed",
  expired: "Expired", pay_at_hospital: "Pay at Hospital", cancelled: "Cancelled",
};
export const PAYMENT_STATUS_TONES: Record<string, "success" | "clay" | "neutral"> = {
  paid: "success", pending: "clay", partially_paid: "clay", failed: "neutral",
  expired: "neutral", pay_at_hospital: "clay", cancelled: "neutral",
};

export const METHOD_LABELS: Record<string, string> = {
  online: "Online", pay_at_hospital: "Pay at Hospital", cash: "Cash", card: "Card", upi: "UPI",
};

export function createBillingOverviewColumns(onSelect: (row: BillingRow) => void): ColumnDef<BillingRow>[] {
  return [
    { id: "invoice_ref", header: "Invoice / Ref.", cell: ({ row }) => (
      <button type="button" onClick={() => onSelect(row.original)} className="text-left">
        <p className="text-brand-700 font-mono text-[12px] font-semibold hover:underline">{row.original.invoice_ref}</p>
        {row.original.prescription_id && <p className="text-hint text-[11px]">RX-{row.original.prescription_id}</p>}
      </button>
    ) },
    { id: "patient_name", header: "Patient", cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.patient_name}</span> },
    { id: "bill_type", header: "Bill Type", cell: ({ row }) => (
      <Badge tone={BILL_TYPE_TONES[row.original.bill_type]}>{BILL_TYPE_LABELS[row.original.bill_type]}</Badge>
    ) },
    { id: "amount", header: "Amount", cell: ({ row }) => <span className="text-ink-900 font-semibold">{formatINR(row.original.amount)}</span> },
    { id: "payment_status", header: "Payment", cell: ({ row }) => {
      const r = row.original;
      if (r.refund_amount > 0) return <Badge tone="clay">₹{r.refund_amount} refunded</Badge>;
      return <Badge tone={PAYMENT_STATUS_TONES[r.payment_status] ?? "neutral"}>{PAYMENT_STATUS_LABELS[r.payment_status] ?? r.payment_status}</Badge>;
    } },
    { id: "method", header: "Method", cell: ({ row }) => <span className="text-ink-600">{row.original.method ? (METHOD_LABELS[row.original.method] ?? row.original.method) : "—"}</span> },
    { id: "date", header: "Date", cell: ({ row }) => <span className="text-ink-600">{formatShortDateTime(row.original.date)}</span> },
    { id: "actions", header: "Action", enableHiding: false, cell: ({ row }) => (
      <button type="button" onClick={() => onSelect(row.original)} className="border-line text-ink-700 px-space-3 py-space-1 rounded-md border text-[12px] font-semibold hover:bg-black/4">
        View
      </button>
    ) },
  ];
}
