"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import type { PharmacySale } from "@/hooks/usePharmacyBilling";

export const SALE_STATUS_LABELS: Record<PharmacySale["payment_status"], string> = {
  pending: "Pending", paid: "Paid", partially_paid: "Partially Paid", cancelled: "Cancelled",
};
export const SALE_STATUS_TONES: Record<PharmacySale["payment_status"], "success" | "clay" | "neutral"> = {
  pending: "clay", paid: "success", partially_paid: "clay", cancelled: "neutral",
};
export const SALE_TYPE_LABELS: Record<PharmacySale["sale_type"], string> = {
  prescription: "Prescription", otc: "OTC Sale", ipd: "IPD Bill",
};
export const SALE_TYPE_TONES: Record<PharmacySale["sale_type"], "clay" | "brand" | "neutral"> = {
  prescription: "clay", otc: "brand", ipd: "neutral",
};

export function createPharmacySaleColumns(): ColumnDef<PharmacySale>[] {
  return [
    { id: "sale_number", header: "Bill No.", cell: ({ row }) => <span className="text-brand-700 font-mono text-[12px] font-semibold">{row.original.sale_number}</span> },
    { id: "sale_type", header: "Type", cell: ({ row }) => (
      <Badge tone={SALE_TYPE_TONES[row.original.sale_type]}>{SALE_TYPE_LABELS[row.original.sale_type]}</Badge>
    ) },
    { id: "patient_name", header: "Patient", cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.patient_name || "Walk-in"}</span> },
    { id: "total_amount", header: "Total", cell: ({ row }) => <span className="text-ink-900 font-semibold">{formatINR(row.original.total_amount)}</span> },
    { id: "created_at", header: "Date", cell: ({ row }) => <span className="text-ink-600">{formatShortDateTime(row.original.created_at)}</span> },
    {
      id: "payment_status",
      header: "Status",
      cell: ({ row }) => <Badge tone={SALE_STATUS_TONES[row.original.payment_status]}>{SALE_STATUS_LABELS[row.original.payment_status]}</Badge>,
    },
  ];
}
