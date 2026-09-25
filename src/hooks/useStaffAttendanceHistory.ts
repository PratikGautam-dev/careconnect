import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";
import type { AttendanceOverviewRow } from "@/hooks/useAttendanceOverview";

export type StaffAttendanceHistoryRecord = Omit<
  AttendanceOverviewRow,
  "staff_id" | "staff_name" | "employee_id" | "role_name" | "is_doctor_role" | "department_name"
>;

export type StaffAttendanceHistoryStaff = {
  id: number;
  name: string;
  role_name: string;
  is_doctor_role: boolean;
};

/** Attendance Overview roster's own drill-down -- one staff member's
 * attendance history, fetched only once a row is actually clicked (staffId
 * starts null). Gated the same way the roster itself is
 * ("attendance_overview" view) via GET /api/portal/attendance/staff/{id},
 * NOT the personal /api/portal/attendance/summary endpoint (that one is
 * always the CALLING principal's own history, never an arbitrary staff_id). */
export function useStaffAttendanceHistory(staffId: number | null) {
  const router = useRouter();

  const { data, error: queryError } = useQuery({
    queryKey: ["portal-staff-attendance-history", staffId],
    enabled: staffId !== null,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch(`/api/portal/attendance/staff/${staffId}?days=90`);
      return unwrapPortalResult<{
        staff: StaffAttendanceHistoryStaff;
        history: StaffAttendanceHistoryRecord[];
      }>(router, result);
    },
  });

  return {
    staff: data?.staff ?? null,
    history: data?.history ?? null,
    error: queryError ? "Couldn't load attendance history — try again." : null,
  };
}
