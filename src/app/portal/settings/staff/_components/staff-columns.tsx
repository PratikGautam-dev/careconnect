"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Phone } from "lucide-react";
import { AVATAR_TINTS } from "@/lib/avatarTints";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import type { StaffMember } from "@/hooks/useStaff";
// Row-level "..." actions menu is commented out below (staff-cellaction.tsx)
// -- View details/Reset password/Activate-Deactivate all now live in the
// detail panel's own Quick Actions instead of being duplicated here.
// import { StaffCellAction } from "./staff-cellaction";

export { AVATAR_TINTS };

// StaffMember (useStaff.ts) is the row type -- department/phone/
// address/reports-to are all real columns. Today's attendance status lives
// on the staff DETAIL panel only (real check-in/out data via
// useAttendanceOverview), not as a table column -- it's a per-day fact, not
// a stable directory field, and repeating it here duplicated the detail
// panel for no benefit.
export type StaffRow = StaffMember;

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

type CreateStaffColumnsOptions = {
  onSelect: (row: StaffRow) => void;
  // Only used by the commented-out "actions" column below.
  // canManage: boolean;
  // togglingId: number | null;
  // onToggleActive: (row: StaffRow) => void;
  // onResetPassword: (row: StaffRow) => void;
};

/** Column defs for the /portal/settings/staff DataTable -- every column
 * here is a real staff_details/identities field. */
export function createStaffColumns({ onSelect }: CreateStaffColumnsOptions): ColumnDef<StaffRow>[] {
  return [
    {
      id: "employee_id",
      header: "Employee ID",
      // "—" for a doctor-role row -- its employee id lives on its linked
      // doctors row instead (Employee ID auto-numbering feature).
      cell: ({ row }) => <span className="text-ink-600">{row.original.employee_id || "—"}</span>,
    },
    {
      id: "name",
      header: "Name",
      cell: ({ row }) => {
        const s = row.original;
        return (
          <button
            type="button"
            onClick={() => onSelect(s)}
            className="gap-space-2 flex items-center text-left"
          >
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                AVATAR_TINTS[row.index % AVATAR_TINTS.length],
              )}
            >
              {initials(s.name)}
            </span>
            <span className="text-ink-900 truncate font-semibold">{s.name}</span>
          </button>
        );
      },
    },
    {
      id: "role",
      header: "Role",
      cell: ({ row }) => <span className="text-ink-600">{row.original.role_name}</span>,
    },
    {
      id: "department",
      header: "Department",
      cell: ({ row }) => (
        <span className="text-ink-600">{row.original.department_name || "—"}</span>
      ),
    },
    {
      id: "phone",
      header: "Phone",
      cell: ({ row }) =>
        row.original.phone ? (
          <span className="text-ink-600 flex items-center gap-1 whitespace-nowrap">
            <Phone size={11} className="text-ink-400" /> {row.original.phone}
          </span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={row.original.is_active ? "success" : "neutral"}>
          {row.original.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },

    // Row-level "..." actions menu -- View details/Reset password/
    // Activate-Deactivate all moved into the detail panel's own Quick
    // Actions instead (StaffDetailPanel.tsx), so this duplicate per-row
    // menu is retired here rather than deleted outright.
    // {
    //   id: "actions",
    //   enableHiding: false,
    //   header: "",
    //   cell: ({ row }) => (
    //     <div className="text-right">
    //       <StaffCellAction
    //         staff={row.original}
    //         canManage={canManage}
    //         togglingId={togglingId}
    //         onSelect={onSelect}
    //         onToggleActive={onToggleActive}
    //         onResetPassword={onResetPassword}
    //       />
    //     </div>
    //   ),
    // },
  ];
}
