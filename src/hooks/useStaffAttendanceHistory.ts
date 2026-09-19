import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import type { AttendanceOverviewRow } from "@/hooks/useAttendanceOverview";

export type StaffAttendanceHistoryRecord = Omit<AttendanceOverviewRow, "staff_id" | "staff_name" | "employee_id" | "role_name" | "is_doctor_role" | "department_name">;

export type StaffAttendanceHistoryStaff = { id: number; name: string; role_name: string; is_doctor_role: boolean };

/** Attendance Overview roster's own drill-down -- one staff member's
 * attendance history, fetched only once a row is actually clicked (staffId
 * starts null). Gated the same way the roster itself is
 * ("attendance_overview" view) via GET /api/portal/attendance/staff/{id},
 * NOT the personal /api/portal/attendance/summary endpoint (that one is
 * always the CALLING principal's own history, never an arbitrary staff_id). */
export function useStaffAttendanceHistory(staffId: number | null) {
  const router = useRouter();
  const [staff, setStaff] = useState<StaffAttendanceHistoryStaff | null>(null);
  const [history, setHistory] = useState<StaffAttendanceHistoryRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (staffId === null) return;
    const result = await staffFetch(`/api/portal/attendance/staff/${staffId}?days=90`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { staff: StaffAttendanceHistoryStaff; history: StaffAttendanceHistoryRecord[] };
    setStaff(data.staff);
    setHistory(data.history);
  }, [router, staffId]);

  useEffect(() => {
    if (staffId !== null) load();
  }, [staffId, load]);

  return { staff, history, error };
}
