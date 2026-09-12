"use client";

import { Building2, Calendar, CalendarDays, CheckCircle2, UserRound, XCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/formatDate";
import type { LeaveRequestRow } from "@/hooks/useLeaveRequests";
import { LEAVE_TYPE_LABELS, ROLE_LABELS, StatusBadge } from "./leave-request-columns";

function DetailRow({ icon: Icon, label, value }: { icon: typeof UserRound; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-space-3 text-[13px]">
      <span className="flex items-center gap-space-2 text-ink-400">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="truncate text-right font-medium text-ink-900">{value}</span>
    </div>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

type Props = {
  request: LeaveRequestRow | null;
  canManage: boolean;
  decidingId: number | null;
  onApprove: (row: LeaveRequestRow) => void;
  onReject: (row: LeaveRequestRow) => void;
};

/** Right-rail "selected leave request" review card -- every field here is
 * real (leave_requests + staff_details/identities, migration
 * 20260912065049). No attachment section -- skipped for now, confirmed
 * with the user. */
export function LeaveRequestDetailPanel({ request, canManage, decidingId, onApprove, onReject }: Props) {
  if (!request) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-center text-[13px] text-ink-400">Select a leave request to review it.</p>
      </Card>
    );
  }

  const applicantLabel = request.role === "doctor" ? `Dr. ${request.applicant_name}` : request.applicant_name;

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex flex-col items-center text-center">
        <span className="mb-space-2 flex h-16 w-16 items-center justify-center rounded-full bg-brand-50 text-[20px] font-bold text-brand-700">
          {initials(request.applicant_name)}
        </span>
        <p className="text-[15px] font-bold text-ink-900">{applicantLabel}</p>
        <p className="text-[12px] text-ink-400">
          {ROLE_LABELS[request.role]} {request.department_name ? `· ${request.department_name}` : ""}
        </p>
      </div>

      <div className="space-y-space-2 border-t border-line pt-space-3">
        <DetailRow icon={CalendarDays} label="Leave Type" value={LEAVE_TYPE_LABELS[request.leave_type]} />
        <DetailRow icon={Calendar} label="From Date" value={formatDate(request.from_date)} />
        <DetailRow icon={Calendar} label="To Date" value={formatDate(request.to_date)} />
        <DetailRow icon={CalendarDays} label="Duration" value={`${request.duration_days} day${request.duration_days === 1 ? "" : "s"}`} />
        <DetailRow icon={Calendar} label="Submitted On" value={formatDate(request.submitted_at)} />
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-ink-400">Status</span>
          <StatusBadge status={request.status} />
        </div>
      </div>

      <div className="mt-space-3 rounded-md border border-line bg-paper p-space-3">
        <p className="mb-space-1 text-[11px] font-semibold text-ink-400">Reason for Leave</p>
        <p className="text-[13px] text-ink-900">{request.reason || "No reason given."}</p>
      </div>

      <div className="mt-space-2 rounded-md border border-line bg-paper p-space-3">
        <p className="mb-space-1 flex items-center gap-space-1 text-[11px] font-semibold text-ink-400">
          <Building2 size={12} /> Reporting Manager
        </p>
        <p className="truncate text-[13px] font-bold text-ink-900">{request.reports_to_name || "—"}</p>
      </div>

      {request.status !== "pending" && (
        <p className="text-hint mt-space-2">
          {request.status === "approved" ? "Approved" : "Rejected"} by {request.decided_by_name || "—"}
          {request.decided_at ? ` on ${formatDate(request.decided_at)}` : ""}.
        </p>
      )}

      {canManage && request.status === "pending" && (
        <div className="mt-space-4 flex gap-space-2 border-t border-line pt-space-3">
          <Button
            type="button" size="md" className="flex-1"
            disabled={decidingId === request.id}
            onClick={() => onApprove(request)}
          >
            <CheckCircle2 size={14} /> Approve
          </Button>
          <Button
            type="button" variant="secondary" size="md" className="flex-1"
            disabled={decidingId === request.id}
            onClick={() => onReject(request)}
          >
            <XCircle size={14} /> Reject
          </Button>
        </div>
      )}
    </Card>
  );
}
