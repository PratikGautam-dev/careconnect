"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import type { DemoRequestStatus, ProductDemoRequestRow } from "@/hooks/useAdminProductDemoRequests";

export const STATUS_LABELS: Record<DemoRequestStatus, string> = {
  new: "New",
  contacted: "Contacted",
  scheduled: "Scheduled",
  closed: "Closed",
};
const STATUS_TINT: Record<DemoRequestStatus, string> = {
  new: "bg-clay-100 text-clay-700",
  contacted: "bg-brand-50 text-brand-600",
  scheduled: "bg-success-tint text-success",
  closed: "bg-black/4 text-ink-400",
};

export function StatusBadge({ status }: { status: DemoRequestStatus }) {
  return (
    <span className={cn("px-space-2 rounded-full py-0.5 text-[11px] font-semibold", STATUS_TINT[status])}>
      {STATUS_LABELS[status]}
    </span>
  );
}

type CreateColumnsOptions = {
  onSelect: (row: ProductDemoRequestRow) => void;
};

export function createDemoRequestColumns({
  onSelect,
}: CreateColumnsOptions): ColumnDef<ProductDemoRequestRow>[] {
  return [
    {
      id: "request_number",
      header: "Request #",
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => onSelect(row.original)}
          className="text-ink-900 text-left font-semibold whitespace-nowrap"
        >
          {row.original.request_number}
        </button>
      ),
    },
    {
      id: "name",
      header: "Name",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <button type="button" onClick={() => onSelect(r)} className="text-left">
            <p className="text-ink-900">{r.name}</p>
            <p className="text-ink-400 text-[11.5px]">{r.email}</p>
          </button>
        );
      },
    },
    {
      id: "hospital_name",
      header: "Hospital",
      cell: ({ row }) => <span className="text-ink-600">{row.original.hospital_name || "—"}</span>,
    },
    {
      id: "phone",
      header: "Phone",
      cell: ({ row }) => <span className="text-ink-600">{row.original.phone || "—"}</span>,
    },
    {
      id: "created_at",
      header: "Submitted",
      cell: ({ row }) => <span className="text-ink-600">{formatDate(row.original.created_at)}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
  ];
}
