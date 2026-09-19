"use client";

import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { useLeaveRequests } from "@/hooks/useLeaveRequests";
import { usePermission } from "@/lib/staffAuth";
import { cn } from "@/lib/cn";

const LEAVE_TYPE_LABELS: Record<string, string> = {
  annual: "Annual Leave", sick: "Sick Leave", casual: "Casual Leave",
  maternity: "Maternity Leave", conference: "Conference Leave", personal: "Personal Leave",
};

const MAX_SHOWN = 5;

/** Dashboard's "what needs my attention" widget: pending leave requests,
 * gated behind "leave_requests" view permission so a role without it sees
 * an empty-state message instead of a silently-broken fetch. */
export function DashboardPendingApprovals({ className }: { className?: string }) {
  const canView = usePermission("leave_requests", "view");
  const { requests } = useLeaveRequests(canView);
  const pending = (requests || []).filter((r) => r.status === "pending").slice(0, MAX_SHOWN);

  return (
    <Card className={cn("flex flex-col p-space-4", className)}>
      <div className="mb-space-1 flex shrink-0 items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">Pending approvals</h3>
        {canView && (
          <Link href="/portal/leave-requests" className="text-[11.5px] font-semibold text-brand-600 hover:underline">
            View all →
          </Link>
        )}
      </div>
      {!canView ? (
        <p className="text-hint">You don&apos;t have access to leave requests.</p>
      ) : requests === null ? (
        <p className="text-hint">Loading…</p>
      ) : pending.length === 0 ? (
        <p className="text-hint">Nothing awaiting approval right now.</p>
      ) : (
        <ul className="scrollbar-hide min-h-0 flex-1 space-y-space-3 overflow-y-auto">
          {pending.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-space-2">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-semibold text-ink-900">
                  {r.applicant_name} — {LEAVE_TYPE_LABELS[r.leave_type] || r.leave_type}
                </p>
                <p className="truncate text-[11.5px] text-ink-400">
                  {r.from_date} → {r.to_date} ({r.is_half_day ? "half day" : `${r.duration_days} day${r.duration_days === 1 ? "" : "s"}`})
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-clay-100 px-space-2 py-0.5 text-[11px] font-semibold text-clay-700">
                Pending
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
