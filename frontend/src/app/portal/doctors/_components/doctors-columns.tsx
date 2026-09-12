"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Eye, Mail, MoreHorizontal, Pencil, Phone, Power } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AVATAR_TINTS } from "@/lib/avatarTints";
import { cn } from "@/lib/cn";
import type { Doctor } from "@/hooks/useDoctors";

export { AVATAR_TINTS };

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

type CreateDoctorColumnsOptions = {
  onSelect: (doc: Doctor) => void;
  canManage: boolean;
  togglingId: string | null;
  onToggleActive: (doc: Doctor) => void;
  loadingDoctorForEdit: string | null;
  onEdit: (doc: Doctor) => void;
};

/** Column definitions for the /portal/doctors DataTable. Availability only
 * ever reflects the real is_active flag (Available/Unavailable) -- there's
 * no real-time presence tracking in this schema, so the reference mockup's
 * finer In Consultation/In Surgery states aren't shown here (see the page's
 * own note). Contact's email row shows this doctor's unified-login email
 * (login_email, null until a login is created -- see the detail panel's own
 * "Create login" action); phone is real too (migration 20260911190007).
 * Leave Balance is real too (migration 20260912065049) -- "—" for a doctor
 * with no login yet, since there's no identity to attach a leave request
 * to. */
export function createDoctorColumns({
  onSelect,
  canManage,
  togglingId,
  onToggleActive,
  loadingDoctorForEdit,
  onEdit,
}: CreateDoctorColumnsOptions): ColumnDef<Doctor>[] {
  return [
    {
      id: "index",
      header: "#",
      cell: ({ row }) => <span className="text-ink-400">{row.index + 1}</span>,
    },
    {
      id: "doctor",
      header: "Doctor",
      cell: ({ row }) => {
        const d = row.original;
        return (
          <button type="button" onClick={() => onSelect(d)} className="flex items-center gap-space-2 text-left">
            <span
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-bold",
                AVATAR_TINTS[row.index % AVATAR_TINTS.length],
              )}
            >
              {initials(d.name)}
            </span>
            <div className="min-w-0">
              <p className="truncate font-semibold text-ink-900">{d.name}</p>
              {d.qualification && <p className="truncate text-[11.5px] text-ink-400">{d.qualification}</p>}
            </div>
          </button>
        );
      },
    },
    {
      id: "specialization",
      header: "Specialization",
      cell: ({ row }) => <span className="text-ink-600">{row.original.specialization || "—"}</span>,
    },
    {
      id: "department_name",
      header: "Department",
      cell: ({ row }) => <span className="text-ink-600">{row.original.department_name}</span>,
    },
    {
      id: "employee_id",
      header: "Employee ID",
      cell: ({ row }) => <span className="text-ink-600">{row.original.employee_id || "—"}</span>,
    },
    {
      id: "leave_balance",
      header: "Leave Balance",
      cell: ({ row }) => {
        const d = row.original;
        if (d.leave_balance_total == null) return <span className="text-ink-400">—</span>;
        return (
          <span className="text-ink-600">
            {d.leave_balance_total - (d.leave_balance_used ?? 0)} / {d.leave_balance_total} days
          </span>
        );
      },
    },
    {
      id: "availability",
      header: "Availability",
      cell: ({ row }) => (
        <span
          className={cn(
            "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
            row.original.is_active ? "bg-success-tint text-success" : "bg-black/4 text-ink-600",
          )}
        >
          {row.original.is_active ? "Available" : "Unavailable"}
        </span>
      ),
    },
    {
      id: "contact",
      header: "Contact",
      cell: ({ row }) => {
        const d = row.original;
        return (
          <div className="space-y-0.5 text-[12px]">
            <p className="flex items-center gap-1 text-ink-600">
              <Phone size={11} /> {d.phone || "—"}
            </p>
            <p className="flex items-center gap-1 text-ink-600">
              <Mail size={11} /> {d.login_email || "No login yet"}
            </p>
          </div>
        );
      },
    },
    {
      id: "actions",
      enableHiding: false,
      header: "Actions",
      cell: ({ row }) => {
        const d = row.original;
        return (
          <div onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-600 hover:bg-black/4 hover:text-ink-900"
                aria-label={`Actions for Dr. ${d.name}`}
              >
                <MoreHorizontal size={16} />
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Actions</DropdownMenuLabel>
                  <DropdownMenuItem onClick={() => onSelect(d)}>
                    <Eye size={14} /> View profile
                  </DropdownMenuItem>
                  {canManage && (
                    <>
                      <DropdownMenuItem disabled={loadingDoctorForEdit === d.id} onClick={() => onEdit(d)}>
                        <Pencil size={14} /> Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem disabled={togglingId === d.id} onClick={() => onToggleActive(d)}>
                        <Power size={14} /> Mark {d.is_active ? "unavailable" : "available"}
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];
}
