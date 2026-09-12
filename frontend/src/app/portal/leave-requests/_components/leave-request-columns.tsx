"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Check, MoreHorizontal, X } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import type { LeaveRequestRole, LeaveRequestRow, LeaveRequestStatus, LeaveType } from "@/hooks/useLeaveRequests";

export const ROLE_LABELS: Record<LeaveRequestRole, string> = { admin: "Admin", receptionist: "Staff", doctor: "Doctor" };
export const LEAVE_TYPE_LABELS: Record<LeaveType, string> = {
  casual: "Casual Leave", sick: "Sick Leave", annual: "Annual Leave",
  maternity: "Maternity Leave", conference: "Conference Leave", personal: "Personal Leave",
};
export const STATUS_LABELS: Record<LeaveRequestStatus, string> = {
  pending: "Pending", approved: "Approved", rejected: "Rejected",
};
const STATUS_TINT: Record<LeaveRequestStatus, string> = {
  pending: "bg-clay-100 text-clay-700",
  approved: "bg-success-tint text-success",
  rejected: "bg-error-tint text-error",
};

export function StatusBadge({ status }: { status: LeaveRequestStatus }) {
  return (
    <span className={cn("rounded-full px-space-2 py-0.5 text-[11px] font-semibold", STATUS_TINT[status])}>
      {STATUS_LABELS[status]}
    </span>
  );
}

type CreateColumnsOptions = {
  onSelect: (row: LeaveRequestRow) => void;
  canManage: boolean;
  decidingId: number | null;
  onApprove: (row: LeaveRequestRow) => void;
  onReject: (row: LeaveRequestRow) => void;
};

export function createLeaveRequestColumns({
  onSelect, canManage, decidingId, onApprove, onReject,
}: CreateColumnsOptions): ColumnDef<LeaveRequestRow>[] {
  return [
    {
      id: "applicant",
      header: "Applicant",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <button type="button" onClick={() => onSelect(r)} className="text-left">
            <p className="font-semibold text-ink-900">{r.role === "doctor" ? `Dr. ${r.applicant_name}` : r.applicant_name}</p>
          </button>
        );
      },
    },
    { id: "role", header: "Role", cell: ({ row }) => <span className="text-ink-600">{ROLE_LABELS[row.original.role]}</span> },
    {
      id: "department",
      header: "Department",
      cell: ({ row }) => <span className="text-ink-600">{row.original.department_name || "—"}</span>,
    },
    {
      id: "leave_type",
      header: "Leave Type",
      cell: ({ row }) => <span className="text-ink-600">{LEAVE_TYPE_LABELS[row.original.leave_type]}</span>,
    },
    { id: "from_date", header: "From Date", cell: ({ row }) => <span className="text-ink-600">{formatDate(row.original.from_date)}</span> },
    { id: "to_date", header: "To Date", cell: ({ row }) => <span className="text-ink-600">{formatDate(row.original.to_date)}</span> },
    {
      id: "duration",
      header: "Duration",
      cell: ({ row }) => <span className="text-ink-600">{row.original.duration_days} day{row.original.duration_days === 1 ? "" : "s"}</span>,
    },
    { id: "submitted", header: "Submitted", cell: ({ row }) => <span className="text-ink-600">{formatDate(row.original.submitted_at)}</span> },
    { id: "status", header: "Status", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    {
      id: "actions",
      enableHiding: false,
      header: "Actions",
      cell: ({ row }) => {
        const r = row.original;
        if (!canManage) return null;
        if (r.status !== "pending") {
          return (
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-600 hover:bg-black/4 hover:text-ink-900"
                  aria-label={`Actions for ${r.applicant_name}`}
                >
                  <MoreHorizontal size={16} />
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>Actions</DropdownMenuLabel>
                    <DropdownMenuItem onClick={() => onSelect(r)}>View details</DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        }
        return (
          <div onClick={(e) => e.stopPropagation()} className="flex items-center gap-space-1">
            <button
              type="button"
              onClick={() => onApprove(r)}
              disabled={decidingId === r.id}
              title="Approve"
              className="flex h-7 w-7 items-center justify-center rounded-md text-success hover:bg-success-tint disabled:opacity-50"
            >
              <Check size={15} />
            </button>
            <button
              type="button"
              onClick={() => onReject(r)}
              disabled={decidingId === r.id}
              title="Reject"
              className="flex h-7 w-7 items-center justify-center rounded-md text-error hover:bg-error-tint disabled:opacity-50"
            >
              <X size={15} />
            </button>
          </div>
        );
      },
    },
  ];
}
