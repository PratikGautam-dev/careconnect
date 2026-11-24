"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/formatDate";
import type { Medicine } from "@/hooks/usePharmacyMedicines";
import { MedicineCellAction } from "./medicines-cellaction";

type Options = {
  onEdit: (medicine: Medicine) => void;
  onToggleActive: (medicine: Medicine) => void;
};

export function createMedicineColumns({ onEdit, onToggleActive }: Options): ColumnDef<Medicine>[] {
  return [
    {
      id: "name",
      header: "Medicine",
      cell: ({ row }) => {
        const m = row.original;
        return (
          <div>
            <p className="text-ink-900 font-semibold">{m.name}</p>
            {m.generic_name && <p className="text-ink-400 text-[11.5px]">{m.generic_name}</p>}
          </div>
        );
      },
    },
    { id: "category", header: "Category", cell: ({ row }) => <span className="text-ink-600">{row.original.category || "—"}</span> },
    { id: "unit", header: "Unit", cell: ({ row }) => <span className="text-ink-600">{row.original.unit}</span> },
    {
      id: "unit_price",
      header: "Unit Price",
      cell: ({ row }) => <span className="text-ink-600">{row.original.unit_price != null ? `₹${row.original.unit_price}` : "—"}</span>,
    },
    {
      id: "stock",
      header: "Stock",
      cell: ({ row }) => {
        const m = row.original;
        const low = m.quantity_on_hand < m.reorder_level;
        return (
          <Badge tone={low ? "clay" : "success"}>
            {m.quantity_on_hand} {m.unit}
            {low ? " · Low" : ""}
          </Badge>
        );
      },
    },
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
      cell: ({ row }) => <Badge tone={row.original.is_active ? "success" : "neutral"}>{row.original.is_active ? "Active" : "Inactive"}</Badge>,
    },
    {
      id: "actions",
      enableHiding: false,
      header: "Actions",
      cell: ({ row }) => <MedicineCellAction medicine={row.original} onEdit={onEdit} onToggleActive={onToggleActive} />,
    },
  ];
}
