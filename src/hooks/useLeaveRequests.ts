import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export type LeaveRequestStatus = "pending" | "approved" | "rejected";
// A hospital-configurable name (Settings -> Leave Policy), not a fixed
// enum -- see db/repositories/leave_requests.py's own DEFAULT_LEAVE_TYPES
// and migration 20260919180000 for why this stopped being a closed set.
export type LeaveType = string;

// A request submitted before that migration still has one of the old
// hardcoded lowercase codes stored (leave_type is plain text, never
// rewritten retroactively) -- shown as its nicer Title Case label rather
// than the raw code; anything else (an admin-configured name, already
// human-readable) is shown exactly as stored.
const LEGACY_LEAVE_TYPE_LABELS: Record<string, string> = {
  casual: "Casual Leave",
  sick: "Sick Leave",
  annual: "Annual Leave",
  maternity: "Maternity Leave",
  conference: "Conference Leave",
  personal: "Personal Leave",
};

export function formatLeaveTypeLabel(leaveType: string): string {
  return LEGACY_LEAVE_TYPE_LABELS[leaveType] || leaveType;
}

export type LeaveRequestRow = {
  id: number;
  applicant_id: number;
  applicant_name: string;
  role_name: string;
  is_doctor_role: boolean;
  department_name: string | null;
  reports_to_name: string | null;
  leave_type: LeaveType;
  from_date: string;
  to_date: string;
  is_half_day: boolean;
  duration_days: number;
  reason: string | null;
  status: LeaveRequestStatus;
  submitted_at: string;
  decided_at: string | null;
  decided_by_name: string | null;
};

export type LeaveRequestSummary = {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  on_leave_today: number;
};

/** Leave Requests admin page -- loads the pending/approved/rejected review
 * queue for the caller's own hospital and owns the approve/reject actions.
 * Rows are submitted through the Holiday Application page
 * (useHolidayApplication.ts) by any staff member, not just a doctor. */
export function useLeaveRequests(canView: boolean) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-leave-requests"],
    enabled: canView,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/leave-requests");
      return unwrapPortalResult<{ requests: LeaveRequestRow[]; summary: LeaveRequestSummary }>(
        router,
        result,
      );
    },
  });

  const decideMutation = useMutation({
    mutationFn: async ({
      requestId,
      action,
    }: {
      requestId: number;
      action: "approve" | "reject";
    }) => {
      const result = await staffFetch(`/api/portal/leave-requests/${requestId}/${action}`, {
        method: "POST",
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  const [decidingId, setDecidingId] = useState<number | null>(null);
  async function decide(request: LeaveRequestRow, action: "approve" | "reject") {
    setDecidingId(request.id);
    try {
      await decideMutation.mutateAsync({ requestId: request.id, action });
      toast.success(`Leave request ${action === "approve" ? "approved" : "rejected"}`);
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error(`Couldn't ${action} leave request`, err.message);
    } finally {
      setDecidingId(null);
    }
  }

  return {
    requests: data?.requests ?? null,
    summary: data?.summary ?? null,
    error: queryError ? "Couldn't load leave requests — try again." : null,
    decidingId,
    load: refetch,
    approve: (r: LeaveRequestRow) => decide(r, "approve"),
    reject: (r: LeaveRequestRow) => decide(r, "reject"),
  };
}
