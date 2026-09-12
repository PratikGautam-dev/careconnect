import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

export type LeaveRequestRole = "admin" | "receptionist" | "doctor";
export type LeaveRequestStatus = "pending" | "approved" | "rejected";
export type LeaveType = "casual" | "sick" | "annual" | "maternity" | "conference" | "personal";

export type LeaveRequestRow = {
  id: number;
  applicant_id: number;
  applicant_name: string;
  role: LeaveRequestRole;
  department_name: string | null;
  reports_to_name: string | null;
  leave_type: LeaveType;
  from_date: string;
  to_date: string;
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

/** Leave Requests admin page (migration 20260912065049) -- loads the
 * pending/approved/rejected review queue for the caller's own hospital and
 * owns the approve/reject actions. No create action here yet -- doctor/
 * staff self-service is a later page (confirmed with the user); every row
 * shown today was created directly against the backend for testing. */
export function useLeaveRequests(canView: boolean) {
  const router = useRouter();

  const [requests, setRequests] = useState<LeaveRequestRow[] | null>(null);
  const [summary, setSummary] = useState<LeaveRequestSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/leave-requests");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { requests: LeaveRequestRow[]; summary: LeaveRequestSummary };
    setRequests(data.requests);
    setSummary(data.summary);
  }, [router]);

  useEffect(() => {
    if (!canView) return;
    load();
  }, [canView, load]);

  async function decide(request: LeaveRequestRow, action: "approve" | "reject") {
    setDecidingId(request.id);
    const result = await staffFetch(`/api/portal/leave-requests/${request.id}/${action}`, { method: "POST" });
    setDecidingId(null);
    if (result.ok) {
      toast.success(`Leave request ${action === "approve" ? "approved" : "rejected"}`);
      load();
    } else if (result.unauthorized) {
      router.push("/portal/login");
    } else {
      toast.error(`Couldn't ${action} leave request`, result.error);
    }
  }

  return {
    requests, summary, error, decidingId, load,
    approve: (r: LeaveRequestRow) => decide(r, "approve"),
    reject: (r: LeaveRequestRow) => decide(r, "reject"),
  };
}
