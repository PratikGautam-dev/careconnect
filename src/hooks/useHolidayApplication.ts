import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import type { LeaveRequestRow, LeaveType } from "@/hooks/useLeaveRequests";

export type LeaveBalance = { quota_days: number; used_days: number; remaining_days: number };

export type SubmitLeaveRequestInput = {
  leave_type: LeaveType;
  from_date: string;
  to_date: string;
  is_half_day: boolean;
  reason: string;
};

/** Any staff member's own leave requests + balance, and the submit action.
 * Feeds the same leave_requests table the admin Leave Requests page
 * (useLeaveRequests.ts) reviews -- gated by a separate permission
 * ("holiday_application", not "leave_requests"), since submitting your own
 * leave and reviewing everyone else's are different capabilities. */
export function useHolidayApplication(canView: boolean) {
  const router = useRouter();
  const [requests, setRequests] = useState<LeaveRequestRow[] | null>(null);
  const [balance, setBalance] = useState<LeaveBalance | null>(null);
  const [leaveTypes, setLeaveTypes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/leave-requests/mine");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as {
      requests: LeaveRequestRow[];
      balance: LeaveBalance;
      leave_types: string[];
    };
    setRequests(data.requests);
    setBalance(data.balance);
    setLeaveTypes(data.leave_types);
  }, [router]);

  useEffect(() => {
    if (!canView) return;
    load();
  }, [canView, load]);

  /** Returns an error string on failure, null on success (mirrors this
   * codebase's own established convention for a form submit action). */
  async function submit(input: SubmitLeaveRequestInput): Promise<string | null> {
    setSubmitting(true);
    const result = await staffFetch("/api/portal/leave-requests/mine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    setSubmitting(false);
    if (!result.ok) {
      if (result.unauthorized) {
        router.push("/portal/login");
        return null;
      }
      return result.error;
    }
    toast.success("Leave application submitted");
    load();
    return null;
  }

  return { requests, balance, leaveTypes, error, submitting, submit, load };
}
