"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Building2, MoreHorizontal, Pencil } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DepartmentDetail } from "@/hooks/useDepartments";
import { AVATAR_TINTS } from "@/lib/avatarTints";

export function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <Badge tone={isActive ? "success" : "clay"} className={!isActive ? "bg-error-tint text-error" : undefined}>
      {isActive ? "Active" : "Inactive"}
    </Badge>
  );
}

type CreateDepartmentColumnsOptions = {
  onSelect: (department: DepartmentDetail) => void;
  onEdit: (department: DepartmentDetail) => void;
  onToggleActive: (department: DepartmentDetail) => void;
};

export function createDepartmentColumns({
  onSelect, onEdit, onToggleActive,
}: CreateDepartmentColumnsOptions): ColumnDef<DepartmentDetail>[] {
  return [
    {
      id: "name",
      header: "Department Name",
      cell: ({ row }) => {
        const d = row.original;
        return (
          <button type="button" onClick={() => onSelect(d)} className="flex items-center gap-space-2 text-left">
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${AVATAR_TINTS[row.index % AVATAR_TINTS.length]}`}>
              <Building2 size={15} />
            </span>
            <span className="font-semibold text-ink-900">{d.name}</span>
          </button>
        );
      },
    },
    {
      id: "head",
      header: "Head of Department",
      cell: ({ row }) => {
        const head = row.original.head_doctor;
        if (!head) return <span className="text-ink-400">—</span>;
        return (
          <div>
            <p className="font-medium text-ink-900">{head.name}</p>
            <p className="text-[11.5px] text-ink-400">{head.qualification}</p>
          </div>
        );
      },
    },
    {
      id: "floor_wing",
      header: "Floor / Wing",
      cell: ({ row }) => row.original.floor_wing || <span className="text-ink-400">—</span>,
    },
    {
      id: "consultation_hours",
      header: "Consultation Hours",
      cell: ({ row }) => row.original.consultation_hours || <span className="text-ink-400">—</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge isActive={row.original.is_active} />,
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const d = row.original;
        return (
          <div onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger
                title="More actions"
                className="flex h-7 w-7 items-center justify-center rounded-md text-ink-400 hover:bg-black/[0.04] hover:text-ink-900"
              >
                <MoreHorizontal size={15} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onEdit(d)}>
                  <Pencil size={13} /> Edit Department
                </DropdownMenuItem>
                <DropdownMenuItem
                  variant={d.is_active ? "destructive" : undefined}
                  onClick={() => onToggleActive(d)}
                >
                  {d.is_active ? "Deactivate" : "Activate"}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];
}
