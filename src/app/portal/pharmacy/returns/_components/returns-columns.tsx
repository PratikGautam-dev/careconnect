"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import type { PurchaseReturn, ReturnStatus, SalesReturn, StockAdjustment } from "@/hooks/usePharmacyReturns";

export type ReturnRow = SalesReturn | PurchaseReturn | StockAdjustment;

export const RETURN_TYPE_LABELS: Record<ReturnRow["type"], string> = {
  sales_return: "Sales Return",
  purchase_return: "Purchase Return",
  stock_adjustment: "Stock Adjustment",
};
export const RETURN_TYPE_TONES: Record<ReturnRow["type"], "clay" | "brand" | "neutral"> = {
  sales_return: "clay",
  purchase_return: "brand",
  stock_adjustment: "neutral",
};

export const RETURN_STATUS_LABELS: Record<ReturnStatus, string> = {
  pending: "Pending", completed: "Completed", cancelled: "Cancelled",
};
export const RETURN_STATUS_TONES: Record<ReturnStatus, "success" | "clay" | "neutral"> = {
  pending: "clay", completed: "success", cancelled: "neutral",
};

export function createReturnColumns(): ColumnDef<ReturnRow>[] {
  return [
    { id: "return_number", header: "Return No.", cell: ({ row }) => (
      <span className="text-brand-700 font-mono text-[12px] font-semibold">{row.original.return_number}</span>
    ) },
    { id: "type", header: "Type", cell: ({ row }) => (
      <Badge tone={RETURN_TYPE_TONES[row.original.type]}>{RETURN_TYPE_LABELS[row.original.type]}</Badge>
    ) },
    { id: "reference_label", header: "Reference No.", cell: ({ row }) => (
      <span className="text-ink-600 font-mono text-[12px]">{row.original.reference_label}</span>
    ) },
    { id: "party_label", header: "Patient / Supplier", cell: ({ row }) => (
      <span className="text-ink-900 font-semibold">{row.original.party_label}</span>
    ) },
    { id: "amount", header: "Amount", cell: ({ row }) => (
      <span className="text-ink-900">{formatINR(row.original.amount)}</span>
    ) },
    { id: "created_at", header: "Date", cell: ({ row }) => (
      <span className="text-ink-600">{formatShortDateTime(row.original.created_at)}</span>
    ) },
    { id: "status", header: "Status", cell: ({ row }) => (
      <Badge tone={RETURN_STATUS_TONES[row.original.status]}>{RETURN_STATUS_LABELS[row.original.status]}</Badge>
    ) },
  ];
}
