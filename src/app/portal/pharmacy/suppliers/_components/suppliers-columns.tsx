"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import type { Supplier } from "@/hooks/usePharmacySuppliers";
import { SupplierCellAction } from "./suppliers-cellaction";

export function createSupplierColumns(onEdit: (supplier: Supplier) => void): ColumnDef<Supplier>[] {
  return [
    { id: "name", header: "Supplier", cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.name}</span> },
    { id: "contact_person", header: "Contact", cell: ({ row }) => <span className="text-ink-600">{row.original.contact_person || "—"}</span> },
    { id: "phone", header: "Phone", cell: ({ row }) => <span className="text-ink-600">{row.original.phone || "—"}</span> },
    { id: "email", header: "Email", cell: ({ row }) => <span className="text-ink-600">{row.original.email || "—"}</span> },
    { id: "category", header: "Category", cell: ({ row }) => <span className="text-ink-600">{row.original.category || "—"}</span> },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <Badge tone={row.original.is_active ? "success" : "neutral"}>{row.original.is_active ? "Active" : "Inactive"}</Badge>,
    },
    {
      id: "actions",
      enableHiding: false,
      header: "Actions",
      cell: ({ row }) => <SupplierCellAction supplier={row.original} onEdit={onEdit} />,
    },
  ];
}
