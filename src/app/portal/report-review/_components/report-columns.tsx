"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Check, Eye, MoreHorizontal, Undo2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AVATAR_TINTS } from "@/lib/avatarTints";
import { cn } from "@/lib/cn";
import type { MockReport, ReportPriority, ReportStatus } from "./mock-reports";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

const PRIORITY_TONE: Record<ReportPriority, "clay" | "success" | "brand"> = {
  Normal: "success",
  High: "clay",
  Urgent: "clay",
};

const STATUS_TONE: Record<ReportStatus, "clay" | "success" | "brand"> = {
  Pending: "clay",
  Approved: "success",
  Rejected: "clay",
};

export function PriorityBadge({ priority }: { priority: ReportPriority }) {
  return (
    <Badge tone={PRIORITY_TONE[priority]} className={priority === "Urgent" ? "bg-error-tint text-error" : undefined}>
      {priority}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: ReportStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]} className={status === "Rejected" ? "bg-error-tint text-error" : undefined}>
      {status}
    </Badge>
  );
}

type CreateReportColumnsOptions = {
  onSelect: (report: MockReport) => void;
  onApprove: (report: MockReport) => void;
  onReturn: (report: MockReport) => void;
  onDelete: (report: MockReport) => void;
  onToggleUrgent: (report: MockReport) => void;
};

/** Column definitions for the /portal/report-review DataTable. Everything
 * here is mock (see mock-reports.ts) -- there's no backend for report
 * review yet, per the user's own "no backend, only frontend" instruction --
 * so approve/return/delete/flag all just mutate the page's own local state,
 * not a real API call. */
export function createReportColumns({
  onSelect,
  onApprove,
  onReturn,
  onDelete,
  onToggleUrgent,
}: CreateReportColumnsOptions): ColumnDef<MockReport>[] {
  return [
    {
      id: "index",
      header: "#",
      cell: ({ row }) => <span className="text-ink-400">{row.index + 1}</span>,
    },
    {
      id: "patient",
      header: "Patient Name",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <button type="button" onClick={() => onSelect(r)} className="flex items-center gap-space-2 text-left">
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                AVATAR_TINTS[row.index % AVATAR_TINTS.length],
              )}
            >
              {initials(r.patientName)}
            </span>
            <div className="min-w-0">
              <p className="truncate font-semibold text-ink-900">{r.patientName}</p>
              <p className="truncate text-[11.5px] text-ink-400">
                {r.age} yrs, {r.gender}
              </p>
            </div>
          </button>
        );
      },
    },
    { id: "reportType", header: "Report Type", cell: ({ row }) => row.original.reportType },
    {
      id: "uploadedBy",
      header: "Uploaded By",
      cell: ({ row }) => (
        <div>
          <p className="text-ink-900">{row.original.uploadedBy}</p>
          <p className="text-[11.5px] text-ink-400">({row.original.uploadedByRole})</p>
        </div>
      ),
    },
    { id: "uploadDate", header: "Upload Date", cell: ({ row }) => row.original.uploadDate },
    { id: "priority", header: "Priority", cell: ({ row }) => <PriorityBadge priority={row.original.priority} /> },
    {
      id: "reviewingDoctor",
      header: "Reviewing Doctor",
      cell: ({ row }) => (
        <div>
          <p className="text-ink-900">{row.original.reviewingDoctor}</p>
          <p className="text-[11.5px] text-ink-400">({row.original.reviewingDoctorSpecialty})</p>
        </div>
      ),
    },
    { id: "status", header: "Status", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div className="flex items-center gap-space-1" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => onSelect(r)}
              title="View report"
              className="flex h-7 w-7 items-center justify-center rounded-md text-ink-400 hover:bg-black/[0.04] hover:text-ink-900"
            >
              <Eye size={15} />
            </button>
            <button
              type="button"
              onClick={() => onApprove(r)}
              disabled={r.status === "Approved"}
              title="Approve"
              className="flex h-7 w-7 items-center justify-center rounded-md text-success hover:bg-success-tint disabled:pointer-events-none disabled:opacity-40"
            >
              <Check size={15} />
            </button>
            <button
              type="button"
              onClick={() => onReturn(r)}
              disabled={r.status === "Rejected"}
              title="Return"
              className="flex h-7 w-7 items-center justify-center rounded-md text-error hover:bg-error-tint disabled:pointer-events-none disabled:opacity-40"
            >
              <Undo2 size={15} />
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger
                title="More actions"
                className="flex h-7 w-7 items-center justify-center rounded-md text-ink-400 hover:bg-black/[0.04] hover:text-ink-900"
              >
                <MoreHorizontal size={15} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onToggleUrgent(r)}>
                  {r.priority === "Urgent" ? "Unmark urgent" : "Flag as urgent"}
                </DropdownMenuItem>
                <DropdownMenuItem variant="destructive" onClick={() => onDelete(r)}>
                  Delete report
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];
}
