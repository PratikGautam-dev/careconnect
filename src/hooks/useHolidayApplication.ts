import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
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

export type HolidayApplicationInitialData = {
  requests: LeaveRequestRow[];
  balance: LeaveBalance;
  leaveTypes: string[];
};

/** Any staff member's own leave requests + balance, and the submit action.
 * Feeds the same leave_requests table the admin Leave Requests page
 * (useLeaveRequests.ts) reviews -- gated by a separate permission
 * ("holiday_application", not "leave_requests"), since submitting your own
 * leave and reviewing everyone else's are different capabilities.
 *
 * `initialData`, when given, seeds requests/balance/leaveTypes straight
 * from it and SKIPS this hook's own mount-time GET
 * /api/portal/leave-requests/mine -- StaffDashboardView.tsx passes this in,
 * already having that same data from its single GET /api/portal/staff/
 * dashboard fetch, so this hook doesn't fire a second, redundant request.
 * Once this hook's OWN fetch has run even once (e.g. after `submit()`
 * calls `load()`), that fetched data takes over as the source of truth
 * going forward -- `initialData` only ever seeds the very first render.
 * The dedicated /portal/holiday-application page (HolidayApplicationView)
 * calls this hook with no second argument, so it keeps doing its own
 * independent fetch exactly as before. */
export function useHolidayApplication(
  canView: boolean,
  initialData?: HolidayApplicationInitialData,
) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-holiday-application-mine"],
    enabled: canView && !initialData,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/leave-requests/mine");
      const fetched = unwrapPortalResult<{
        requests: LeaveRequestRow[];
        balance: LeaveBalance;
        leave_types: string[];
      }>(router, result);
      return {
        requests: fetched.requests,
        balance: fetched.balance,
        leaveTypes: fetched.leave_types,
      };
    },
  });

  const requests = data?.requests ?? initialData?.requests ?? null;
  const balance = data?.balance ?? initialData?.balance ?? null;
  const leaveTypes = data?.leaveTypes ?? initialData?.leaveTypes ?? [];

  const submitMutation = useMutation({
    mutationFn: async (input: SubmitLeaveRequestInput) => {
      const result = await staffFetch("/api/portal/leave-requests/mine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  /** Returns an error string on failure, null on success (mirrors this
   * codebase's own established convention for a form submit action). */
  async function submit(input: SubmitLeaveRequestInput): Promise<string | null> {
    try {
      await submitMutation.mutateAsync(input);
      toast.success("Leave application submitted");
      refetch();
      return null;
    } catch (err) {
      return isPortalMutationError(err) ? err.message : null;
    }
  }

  return {
    requests,
    balance,
    leaveTypes,
    error: queryError ? "Couldn't load leave requests — try again." : null,
    submitting: submitMutation.isPending,
    submit,
    load: refetch,
  };
}
