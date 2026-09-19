import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import type { LeaveRequestRow } from "@/hooks/useLeaveRequests";

export type StaffLeaveHistoryStaff = { id: number; name: string; role_name: string; is_doctor_role: boolean };
export type StaffLeaveHistoryBalance = { quota_days: number; used_days: number; remaining_days: number };

/** Staff/Doctor detail panels' own "Leave history" quick action -- one
 * staff member's leave requests, fetched only once opened (staffId starts
 * null). Gated by "leave_requests" view (the admin review permission) via
 * GET /api/portal/leave-requests/staff/{id}, NOT the personal
 * /api/portal/leave-requests/mine endpoint (that one is always the CALLING
 * principal's own history, never an arbitrary staff_id) -- same split
 * useStaffAttendanceHistory.ts already follows for attendance. */
export function useStaffLeaveHistory(staffId: number | null) {
  const router = useRouter();
  const [staff, setStaff] = useState<StaffLeaveHistoryStaff | null>(null);
  const [requests, setRequests] = useState<LeaveRequestRow[] | null>(null);
  const [balance, setBalance] = useState<StaffLeaveHistoryBalance | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (staffId === null) return;
    const result = await staffFetch(`/api/portal/leave-requests/staff/${staffId}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as {
      staff: StaffLeaveHistoryStaff;
      requests: LeaveRequestRow[];
      balance: StaffLeaveHistoryBalance;
    };
    setStaff(data.staff);
    setRequests(data.requests);
    setBalance(data.balance);
  }, [router, staffId]);

  useEffect(() => {
    if (staffId !== null) load();
  }, [staffId, load]);

  return { staff, requests, balance, error };
}
