"use client";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useStaffLeaveHistory } from "@/hooks/useStaffLeaveHistory";
import { formatDate } from "@/lib/formatDate";
import { formatLeaveTypeLabel, type LeaveRequestStatus } from "@/hooks/useLeaveRequests";
import { cn } from "@/lib/cn";

const STATUS_LABELS: Record<LeaveRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

const STATUS_STYLES: Record<LeaveRequestStatus, string> = {
  pending: "bg-clay-100 text-clay-700",
  approved: "bg-success-tint text-success",
  rejected: "bg-error-tint text-error",
};

type Props = {
  staffId: number | null;
  onOpenChange: (open: boolean) => void;
};

/** Staff/Doctor detail panels' drill-down -- clicking "Leave history" opens
 * this with that staff member's full leave request history + balance,
 * rather than sending an admin over to the Leave Requests page and having
 * them search/filter for one person there. Same "modal keeps the detail
 * panel the return point" shape as StaffAttendanceHistoryDialog.tsx. */
export function StaffLeaveHistoryDialog({ staffId, onOpenChange }: Props) {
  const { staff, requests, balance, error } = useStaffLeaveHistory(staffId);

  return (
    <Dialog open={staffId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogTitle>{staff ? staff.name : "Leave history"}</DialogTitle>
        <p className="mb-space-4 text-ink-400 text-[12.5px]">
          {staff ? `${staff.role_name} · ` : ""}
          {balance
            ? `${balance.remaining_days} of ${balance.quota_days} days remaining this year`
            : "Loading balance…"}
        </p>

        {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

        {requests === null ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        ) : requests.length === 0 ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">No leave requests yet.</p>
        ) : (
          <div className="max-h-[60vh] overflow-x-auto overflow-y-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-line text-label text-ink-400 border-b text-left">
                  <th className="py-space-2 pr-space-3 font-medium">Type</th>
                  <th className="py-space-2 pr-space-3 font-medium">From</th>
                  <th className="py-space-2 pr-space-3 font-medium">To</th>
                  <th className="py-space-2 pr-space-3 font-medium">Days</th>
                  <th className="py-space-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id} className="border-line border-b last:border-0">
                    <td className="py-space-3 pr-space-3 text-ink-900 whitespace-nowrap">
                      {formatLeaveTypeLabel(r.leave_type)}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {formatDate(r.from_date)}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {formatDate(r.to_date)}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {r.is_half_day ? "Half" : r.duration_days}
                    </td>
                    <td className="py-space-3">
                      <span
                        className={cn(
                          "px-space-2 rounded-full py-0.5 text-[11px] font-semibold whitespace-nowrap",
                          STATUS_STYLES[r.status],
                        )}
                      >
                        {STATUS_LABELS[r.status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
