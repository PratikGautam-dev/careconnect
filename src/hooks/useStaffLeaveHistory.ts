import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";
import type { LeaveRequestRow } from "@/hooks/useLeaveRequests";

export type StaffLeaveHistoryStaff = {
  id: number;
  name: string;
  role_name: string;
  is_doctor_role: boolean;
};
export type StaffLeaveHistoryBalance = {
  quota_days: number;
  used_days: number;
  remaining_days: number;
};

/** Staff/Doctor detail panels' own "Leave history" quick action -- one
 * staff member's leave requests, fetched only once opened (staffId starts
 * null). Gated by "leave_requests" view (the admin review permission) via
 * GET /api/portal/leave-requests/staff/{id}, NOT the personal
 * /api/portal/leave-requests/mine endpoint (that one is always the CALLING
 * principal's own history, never an arbitrary staff_id) -- same split
 * useStaffAttendanceHistory.ts already follows for attendance. */
export function useStaffLeaveHistory(staffId: number | null) {
  const router = useRouter();

  const { data, error: queryError } = useQuery({
    queryKey: ["portal-staff-leave-history", staffId],
    enabled: staffId !== null,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch(`/api/portal/leave-requests/staff/${staffId}`);
      return unwrapPortalResult<{
        staff: StaffLeaveHistoryStaff;
        requests: LeaveRequestRow[];
        balance: StaffLeaveHistoryBalance;
      }>(router, result);
    },
  });

  return {
    staff: data?.staff ?? null,
    requests: data?.requests ?? null,
    balance: data?.balance ?? null,
    error: queryError ? "Couldn't load leave history — try again." : null,
  };
}
