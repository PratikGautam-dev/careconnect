"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import type { PurchaseOrder } from "@/hooks/usePharmacyPurchaseOrders";

export const PO_STATUS_LABELS: Record<PurchaseOrder["status"], string> = {
  pending: "Pending", in_transit: "In Transit", delivered: "Delivered", delayed: "Delayed", cancelled: "Cancelled",
};
export const PO_STATUS_TONES: Record<PurchaseOrder["status"], "success" | "clay" | "neutral" | "brand"> = {
  pending: "brand", in_transit: "clay", delivered: "success", delayed: "clay", cancelled: "neutral",
};

export function createPurchaseOrderColumns(): ColumnDef<PurchaseOrder>[] {
  return [
    { id: "id", header: "PO #", cell: ({ row }) => <span className="text-ink-600 font-mono text-[12px]">#{row.original.id}</span> },
    { id: "supplier_name", header: "Supplier", cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.supplier_name}</span> },
    { id: "order_date", header: "Order Date", cell: ({ row }) => <span className="text-ink-600">{formatDate(row.original.order_date)}</span> },
    {
      id: "expected_delivery",
      header: "Expected Delivery",
      cell: ({ row }) => <span className="text-ink-600">{row.original.expected_delivery_date ? formatDate(row.original.expected_delivery_date) : "—"}</span>,
    },
    {
      id: "total_amount",
      header: "Total",
      cell: ({ row }) => <span className="text-ink-600">{row.original.total_amount != null ? formatINR(row.original.total_amount) : "—"}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <Badge tone={PO_STATUS_TONES[row.original.status]}>{PO_STATUS_LABELS[row.original.status]}</Badge>,
    },
  ];
}
