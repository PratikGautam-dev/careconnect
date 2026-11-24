"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/formatDate";
import type { Medicine } from "@/hooks/usePharmacyMedicines";

export function createInventoryColumns(): ColumnDef<Medicine>[] {
  return [
    { id: "name", header: "Medicine", cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.name}</span> },
    { id: "category", header: "Category", cell: ({ row }) => <span className="text-ink-600">{row.original.category || "—"}</span> },
    {
      id: "quantity",
      header: "Quantity on Hand",
      cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.quantity_on_hand} {row.original.unit}</span>,
    },
    { id: "reorder_level", header: "Reorder Level", cell: ({ row }) => <span className="text-ink-600">{row.original.reorder_level}</span> },
    {
      id: "nearest_expiry",
      header: "Nearest Expiry",
      cell: ({ row }) => (
        <span className="text-ink-600">{row.original.nearest_expiry_date ? formatDate(row.original.nearest_expiry_date) : "—"}</span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => {
        const m = row.original;
        if (m.quantity_on_hand === 0) return <Badge tone="clay">Out of Stock</Badge>;
        if (m.quantity_on_hand < m.reorder_level) return <Badge tone="clay">Low Stock</Badge>;
        return <Badge tone="success">In Stock</Badge>;
      },
    },
  ];
}
