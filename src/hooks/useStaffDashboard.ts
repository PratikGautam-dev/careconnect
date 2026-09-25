import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import type { LeaveBalance } from "@/hooks/useHolidayApplication";
import type { LeaveRequestRow } from "@/hooks/useLeaveRequests";

export type AttendanceRecord = {
  date: string;
  check_in_at: string | null;
  check_out_at: string | null;
  break_started_at: string | null;
  break_minutes: number;
  status: "on_time" | "late" | "absent" | "leave" | "half_day";
  late_minutes: number;
  working_minutes: number;
  overtime_minutes: number;
  check_in_verified_method: string | null;
};

export type StaffDashboardData = {
  attendance: { today: AttendanceRecord | null; history: AttendanceRecord[] } | null;
  leave: { requests: LeaveRequestRow[]; balance: LeaveBalance; leave_types: string[] } | null;
};

/** Loads the single combined GET /api/portal/staff/dashboard for
 * StaffDashboardView -- same staffFetch/useQuery pattern
 * usePortalDashboard.ts already established. `attendance`/`leave` each
 * come back `null` when their own permission ("check_in_out"/view or
 * "holiday_application"/view respectively) isn't granted -- callers derive
 * `loaded`/`leavePermitted`/etc. off that, same three-state contract the
 * original inline fetch had. */
export function useStaffDashboard() {
  const router = useRouter();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["staff-dashboard"],
    queryFn: async () => {
      const result = await staffFetch("/api/portal/staff/dashboard");
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return result.data as StaffDashboardData;
    },
  });

  return {
    // null both before the first fetch resolves AND if it ever fails
    // (matches the original: `today`/`history`/`leavePermitted` never got
    // set on a failed loadDashboard() beyond the unauthorized redirect).
    data: data ?? null,
    // Flips true once the first fetch settles, success or failure --
    // mirrors the original's own `setLoaded(true)` on both paths.
    loaded: !isLoading,
    refetch,
  };
}
