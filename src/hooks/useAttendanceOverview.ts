import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

// Only these two are admin-settable from the roster's override control --
// Late/On leave stay derived (check-in time / leave approval), matching
// db/repositories/attendance.py's own MANUAL_OVERRIDE_STATUSES.
export type ManualAttendanceStatus = "on_time" | "absent";

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
  /** "ip" | "gps" | "both" | "manual" | "none" -- see lib/attendanceMethod.ts. */
  check_in_verified_method: string | null;
  /** The hospital uses the WiFi check but this person was matched by
   * location only -- worth a look. */
  check_in_needs_review: boolean;
};

export type CheckInRequestRow = {
  id: number;
  staff_id: number;
  staff_name: string | null;
  employee_id: string | null;
  date: string;
  reason: string;
  failure_reason: string | null;
  latitude: number | null;
  longitude: number | null;
  accuracy_meters: number | null;
  status: "pending" | "approved" | "rejected";
  requested_at: string | null;
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

  const {
    data: records,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-attendance-overview", date],
    enabled: canView,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch(`/api/portal/attendance/hospital?for_date=${date}`);
      return unwrapPortalResult<{ records: AttendanceOverviewRow[] }>(router, result).records;
    },
  });

  const overrideMutation = useMutation({
    mutationFn: async ({
      staffId,
      status,
    }: {
      staffId: number;
      status: ManualAttendanceStatus;
    }) => {
      const result = await staffFetch("/api/portal/attendance/hospital/override", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ staff_id: staffId, date, status }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  const [overridingId, setOverridingId] = useState<number | null>(null);
  async function setStatus(row: AttendanceOverviewRow, status: ManualAttendanceStatus) {
    setOverridingId(row.staff_id);
    try {
      await overrideMutation.mutateAsync({ staffId: row.staff_id, status });
      toast.success(`${row.staff_name} marked ${status === "on_time" ? "Present" : "Absent"}`);
      refetch();
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't update attendance", err.message);
    } finally {
      setOverridingId(null);
    }
  }

  const { data: requests, refetch: refetchRequests } = useQuery({
    queryKey: ["portal-attendance-checkin-requests"],
    enabled: canView,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/attendance/requests?status=pending");
      return unwrapPortalResult<{ requests: CheckInRequestRow[] }>(router, result).requests;
    },
  });

  const [reviewingId, setReviewingId] = useState<number | null>(null);
  async function reviewRequest(
    request: CheckInRequestRow,
    action: "approve" | "reject",
    note?: string,
  ) {
    setReviewingId(request.id);
    try {
      const result = await staffFetch(`/api/portal/attendance/requests/${request.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, note: note ?? "" }),
      });
      unwrapPortalResult<unknown>(router, result);
      toast.success(
        action === "approve"
          ? `${request.staff_name ?? "Staff member"} checked in`
          : "Request declined",
      );
      await Promise.all([refetchRequests(), refetch()]);
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't update the request", err.message);
    } finally {
      setReviewingId(null);
    }
  }

  return {
    requests: requests ?? [],
    reviewRequest,
    reviewingId,
    date,
    setDate,
    records: records ?? null,
    error: queryError ? "Couldn't load attendance — try again." : null,
    load: refetch,
    setStatus,
    overridingId,
  };
}
