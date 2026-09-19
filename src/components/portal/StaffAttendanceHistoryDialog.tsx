"use client";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useStaffAttendanceHistory } from "@/hooks/useStaffAttendanceHistory";
import { formatTimeOnly } from "@/lib/formatDate";
import { cn } from "@/lib/cn";
import type { AttendanceOverviewStatus } from "@/hooks/useAttendanceOverview";

const STATUS_LABELS: Record<AttendanceOverviewStatus, string> = {
  on_time: "Present",
  half_day: "Present",
  late: "Late",
  leave: "On leave",
  absent: "Absent",
};

const STATUS_STYLES: Record<AttendanceOverviewStatus, string> = {
  on_time: "bg-success-tint text-success",
  half_day: "bg-success-tint text-success",
  late: "bg-clay-100 text-clay-700",
  leave: "bg-brand-50 text-brand-600",
  absent: "bg-error-tint text-error",
};

function formatMinutes(minutes: number): string {
  if (!minutes) return "-";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
}

function formatDay(dateKey: string): string {
  return new Date(`${dateKey}T00:00:00`).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

type Props = {
  staffId: number | null;
  onOpenChange: (open: boolean) => void;
};

/** Attendance Overview roster's drill-down -- clicking a row opens this
 * with that staff member's last 90 days, rather than navigating away from
 * the day-of-hospital roster (the page's own primary view, see that page's
 * doc comment for why a flat "everyone today" table is the default instead
 * of a master-detail layout). A modal keeps the roster the return point
 * instead of a separate route. */
export function StaffAttendanceHistoryDialog({ staffId, onOpenChange }: Props) {
  const { staff, history, error } = useStaffAttendanceHistory(staffId);

  return (
    <Dialog open={staffId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogTitle>
          {staff ? staff.name : "Attendance history"}
        </DialogTitle>
        {staff && <p className="mb-space-4 text-ink-400 text-[12.5px]">{staff.role_name} · Last 90 days</p>}

        {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

        {history === null ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        ) : history.length === 0 ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">No attendance records yet.</p>
        ) : (
          <div className="max-h-[60vh] overflow-y-auto overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-line text-label text-ink-400 border-b text-left">
                  <th className="py-space-2 pr-space-3 font-medium">Date</th>
                  <th className="py-space-2 pr-space-3 font-medium">Check-in</th>
                  <th className="py-space-2 pr-space-3 font-medium">Check-out</th>
                  <th className="py-space-2 pr-space-3 font-medium">Working hours</th>
                  <th className="py-space-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.date} className="border-line border-b last:border-0">
                    <td className="py-space-3 pr-space-3 text-ink-900 whitespace-nowrap">
                      {formatDay(r.date)}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {r.check_in_at ? formatTimeOnly(r.check_in_at) : "-"}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {r.check_out_at ? formatTimeOnly(r.check_out_at) : "-"}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {formatMinutes(r.working_minutes)}
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
