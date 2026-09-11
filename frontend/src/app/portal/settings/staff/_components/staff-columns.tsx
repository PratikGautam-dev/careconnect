"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Phone } from "lucide-react";
import { AVATAR_TINTS } from "@/lib/avatarTints";
import { cn } from "@/lib/cn";
import type { StaffRole } from "@/lib/staffAuth";
import type { AttendanceStatus, Shift, StaffMember } from "@/hooks/useStaffManagement";
import { StaffCellAction } from "./staff-cellaction";

export { AVATAR_TINTS };

// StaffMember (useStaffManagement.ts) is the row type directly now --
// department/shift/attendance/phone/address/reports-to are all real
// staff_details/identities columns (migration 20260911174439), not mocked.
// Only leave balance/leave workflow remain unbuilt (StaffDetailPanel's own
// note there).
export type StaffRow = StaffMember;

export const ROLE_LABELS: Record<StaffRole, string> = { admin: "Admin", receptionist: "Receptionist", doctor: "Doctor" };

export const SHIFT_LABELS: Record<Shift, string> = {
  day: "Day (8AM - 4PM)", evening: "Evening (4PM - 12AM)", night: "Night (8PM - 8AM)",
};

export const ATTENDANCE_LABELS: Record<AttendanceStatus, string> = {
  present: "Present", on_leave: "On Leave", half_day: "Half Day",
};

const ATTENDANCE_DOT: Record<AttendanceStatus, string> = {
  present: "bg-success", on_leave: "bg-error", half_day: "bg-brand-500",
};
const ATTENDANCE_TEXT: Record<AttendanceStatus, string> = {
  present: "text-success", on_leave: "text-error", half_day: "text-brand-600",
};

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

type CreateStaffColumnsOptions = {
  onSelect: (row: StaffRow) => void;
  canManage: boolean;
  togglingId: number | null;
  onToggleActive: (row: StaffRow) => void;
  onResetPassword: (row: StaffRow) => void;
};

/** Column defs for the /portal/settings/staff DataTable -- every column
 * here is a real staff_details/identities field. */
export function createStaffColumns({
  onSelect, canManage, togglingId, onToggleActive, onResetPassword,
}: CreateStaffColumnsOptions): ColumnDef<StaffRow>[] {
  return [
    {
      id: "name",
      header: "Name",
      cell: ({ row }) => {
        const s = row.original;
        return (
          <button type="button" onClick={() => onSelect(s)} className="flex items-center gap-space-2 text-left">
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                AVATAR_TINTS[row.index % AVATAR_TINTS.length],
              )}
            >
              {initials(s.name)}
            </span>
            <span className="truncate font-semibold text-ink-900">{s.name}</span>
          </button>
        );
      },
    },
    {
      id: "role",
      header: "Role",
      cell: ({ row }) => <span className="text-ink-600">{ROLE_LABELS[row.original.role]}</span>,
    },
    {
      id: "department",
      header: "Department",
      cell: ({ row }) => <span className="text-ink-600">{row.original.department_name || "—"}</span>,
    },
    {
      id: "shift",
      header: "Shift",
      cell: ({ row }) => (
        <span className="whitespace-nowrap text-ink-600">{row.original.shift ? SHIFT_LABELS[row.original.shift] : "—"}</span>
      ),
    },
    {
      id: "attendance",
      header: "Attendance Status",
      cell: ({ row }) => {
        const status = row.original.attendance_status;
        return (
          <span className={cn("flex items-center gap-space-1 text-[12.5px] font-semibold whitespace-nowrap", ATTENDANCE_TEXT[status])}>
            <span className={cn("h-1.5 w-1.5 rounded-full", ATTENDANCE_DOT[status])} /> {ATTENDANCE_LABELS[status]}
          </span>
        );
      },
    },
    {
      id: "phone",
      header: "Phone",
      cell: ({ row }) =>
        row.original.phone ? (
          <span className="flex items-center gap-1 whitespace-nowrap text-ink-600">
            <Phone size={11} className="text-ink-400" /> {row.original.phone}
          </span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      id: "actions",
      enableHiding: false,
      header: "",
      cell: ({ row }) => (
        <div className="text-right">
          <StaffCellAction
            staff={row.original}
            canManage={canManage}
            togglingId={togglingId}
            onSelect={onSelect}
            onToggleActive={onToggleActive}
            onResetPassword={onResetPassword}
          />
        </div>
      ),
    },
  ];
}
