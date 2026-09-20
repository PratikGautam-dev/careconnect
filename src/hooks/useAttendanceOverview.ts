import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";

export type AttendanceOverviewStatus = "on_time" | "late" | "absent" | "leave" | "half_day";

// Shared display strings for this status -- StaffAttendanceHistoryDialog and
// StaffDetailPanel both show the same real check-in/out-derived status, so
// the label/color mapping lives here once instead of being redefined per
// consumer.
export const ATTENDANCE_STATUS_LABELS: Record<AttendanceOverviewStatus, string> = {
  on_time: "Present",
  half_day: "Present",
  late: "Late",
  leave: "On leave",
  absent: "Absent",
};

export const ATTENDANCE_STATUS_STYLES: Record<AttendanceOverviewStatus, string> = {
  on_time: "bg-success-tint text-success",
  half_day: "bg-success-tint text-success",
  late: "bg-clay-100 text-clay-700",
  leave: "bg-brand-50 text-brand-600",
  absent: "bg-error-tint text-error",
};

export type AttendanceOverviewRow = {
  staff_id: number;
  staff_name: string;
  employee_id: string | null;
  role_name: string;
  is_doctor_role: boolean;
  department_name: string | null;
  date: string;
  check_in_at: string | null;
  check_out_at: string | null;
  break_minutes: number;
  status: AttendanceOverviewStatus;
  late_minutes: number;
  working_minutes: number;
  overtime_minutes: number;
};

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Admin-facing "Attendance Overview" page -- every staff member's
 * check-in/out for ONE selected day (default today), fetched from
 * GET /api/portal/attendance/hospital?for_date=, gated by the
 * "attendance_overview" page_key (admin-only by default, separate from the
 * personal "attendance" page a staff member's own history lives behind).
 * A staff member with no attendance_records row for that day still comes
 * back with status "absent" (see db.get_hospital_attendance's own
 * docstring) rather than being omitted, so this is always the FULL roster,
 * never a partial list. */
export function useAttendanceOverview(canView: boolean) {
  const router = useRouter();
  const [date, setDate] = useState(todayKey());
  const [records, setRecords] = useState<AttendanceOverviewRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch(`/api/portal/attendance/hospital?for_date=${date}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setRecords((result.data as { records: AttendanceOverviewRow[] }).records);
  }, [router, date]);

  useEffect(() => {
    if (!canView) return;
    load();
  }, [canView, load]);

  return { date, setDate, records, error, load };
}
