"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { MoreHorizontal, Pencil, Stethoscope } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PROCEDURE_CATEGORIES, type Procedure } from "@/hooks/useProcedures";
import { AVATAR_TINTS } from "@/lib/avatarTints";

function categoryLabel(category: string) {
  return PROCEDURE_CATEGORIES.find((c) => c.value === category)?.label ?? category;
}

function priceRange(min: number | null, max: number | null) {
  if (min == null && max == null) return null;
  if (min != null && max != null && min !== max) return `₹${min} – ₹${max}`;
  return `₹${min ?? max}`;
}

export function ProcedureStatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <Badge
      tone={isActive ? "success" : "clay"}
      className={!isActive ? "bg-error-tint text-error" : undefined}
    >
      {isActive ? "Active" : "Inactive"}
    </Badge>
  );
}

type CreateProcedureColumnsOptions = {
  onEdit: (procedure: Procedure) => void;
  onToggleActive: (procedure: Procedure) => void;
};

export function createProcedureColumns({
  onEdit,
  onToggleActive,
}: CreateProcedureColumnsOptions): ColumnDef<Procedure>[] {
  return [
    {
      id: "name",
      header: "Procedure",
      cell: ({ row }) => {
        const p = row.original;
        return (
          <div className="gap-space-2 flex items-center">
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${AVATAR_TINTS[row.index % AVATAR_TINTS.length]}`}
            >
              <Stethoscope size={15} />
            </span>
            <span className="text-ink-900 font-semibold">{p.name}</span>
          </div>
        );
      },
    },
    {
      id: "category",
      header: "Category",
      cell: ({ row }) => categoryLabel(row.original.category),
    },
    {
      id: "price_range",
      header: "Estimated Price",
      cell: ({ row }) => {
        const range = priceRange(row.original.estimated_price_min, row.original.estimated_price_max);
        return range ?? <span className="text-ink-400">—</span>;
      },
    },
    {
      id: "duration",
      header: "Duration",
      cell: ({ row }) => `${row.original.duration_minutes} min`,
    },
    {
      id: "booking_mode",
      header: "Booking Mode",
      cell: ({ row }) =>
        row.original.booking_mode === "approval_required" ? "Approval Required" : "Instant",
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <ProcedureStatusBadge isActive={row.original.is_active} />,
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const p = row.original;
        return (
          <div onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger
                title="More actions"
                className="text-ink-400 hover:text-ink-900 flex h-7 w-7 items-center justify-center rounded-md hover:bg-black/[0.04]"
              >
                <MoreHorizontal size={15} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onEdit(p)}>
                  <Pencil size={13} /> Edit Procedure
                </DropdownMenuItem>
                <DropdownMenuItem
                  variant={p.is_active ? "destructive" : undefined}
                  onClick={() => onToggleActive(p)}
                >
                  {p.is_active ? "Deactivate" : "Activate"}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];
}
