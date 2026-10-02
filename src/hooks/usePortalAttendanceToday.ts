import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";

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
  check_in_accuracy_meters: number | null;
  /** The hospital uses the WiFi check but this check-in matched by location
   * only -- an admin may want to look at it. */
  check_in_needs_review: boolean;
};

export type CheckInRequestStatus = "pending" | "approved" | "rejected";

/** A staff member's "please approve my check-in" request for today. */
export type CheckInRequest = {
  id: number;
  status: CheckInRequestStatus;
  reason: string;
  requested_at: string | null;
  review_note: string | null;
};

export type PortalAttendanceToday = {
  today: AttendanceRecord | null;
  history: AttendanceRecord[];
  checkin_request: CheckInRequest | null;
};

/** Loads GET /api/portal/attendance/today for CheckInOutPage -- same
 * portalFetch/useQuery pattern usePortalDashboard.ts already established.
 * Only fetches once `enabled` (the page's own `ready && canView` gate) is
 * true, same as the original effect's own `if (ready && canView) load();`
 * guard. Resolves to `null` on failure rather than throwing -- the
 * original silently left `today`/`history` at their initial values on a
 * failed fetch (only `loaded` flipped true), no dedicated error state. */
export function usePortalAttendanceToday(enabled: boolean) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["portal-attendance-today"],
    enabled,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/attendance/today");
      return result.ok ? (result.data as PortalAttendanceToday) : null;
    },
  });

  return {
    data: data ?? null,
    // Mirrors the original's own `loaded` -- false until enabled AND the
    // first fetch has settled (isLoading is also true while `enabled` is
    // false and no data exists yet, matching "hasn't loaded").
    loaded: !isLoading && data !== undefined,
    refetch,
  };
}
