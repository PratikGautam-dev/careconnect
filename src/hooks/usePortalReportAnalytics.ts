import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { useStaffSession } from "@/lib/staffAuth";

/** A stat tile's current-period value plus its %-change vs the prior period
 * of equal length (e.g. "1-30 Sep" vs "1-30 Aug") -- same delta-pct shape
 * usePortalDashboard's stats already use (see StatTile), just named
 * generically here since this hook has four of these instead of one-off
 * `today_x_delta_pct` fields. */
export type ReportAnalyticsStat = {
  value: number;
  /** null when there's no prior-period data to compare against (e.g. a
   * range starting at the hospital's own onboarding date). */
  delta_pct: number | null;
};

export type ReportAnalyticsData = {
  date_from: string; // YYYY-MM-DD, echoes the request
  date_to: string; // YYYY-MM-DD, echoes the request
  prev_date_from: string;
  prev_date_to: string;
  stats: {
    total_appointments: ReportAnalyticsStat;
    total_patients: ReportAnalyticsStat;
    total_revenue: ReportAnalyticsStat;
    /** 0-100 fulfillment-rate proxy: (booked+attended) / (booked+attended+
     * cancelled+no_show) over the range -- see db/repositories/
     * report_analytics.py's compute_occupancy_rate() docstring; NOT true
     * slot-capacity utilization. */
    occupancy_rate: ReportAnalyticsStat;
  };
  /** One point per day in [date_from, date_to] -- Appointment Trends' two
   * series (Appointments, Patients) both read off this same array. */
  appointment_trends: { date: string; appointments: number; patients: number }[];
  department_breakdown: { department_name: string; count: number; revenue: number; pct: number }[];
  visit_type_breakdown: { visit_type: string; count: number; pct: number }[];
  /** One bucket per calendar week that falls (even partially) inside the
   * selected range. */
  weekly_revenue: { week_label: string; week_start: string; week_end: string; revenue: number }[];
  /** Pre-formatted sentences from the backend, e.g. "Appointments increased
   * by 12.5% compared to the previous period." -- rendered split on an em
   * dash into a card title + description when present, so the backend owns
   * the copy/thresholds and this page stays dumb. A plain string with no em
   * dash still renders fine, just as a description-only card. */
  key_insights: string[];
  top_departments: { department_name: string; appointment_count: number; revenue: number }[];
};

/** Loads /portal/report-analytics for the given [dateFrom, dateTo] window --
 * same portalFetch + useQuery pattern as usePortalDashboard.ts, minus the
 * polling (that hook's 20s poll exists because new WhatsApp/staff bookings
 * need to show up on today's live dashboard without a manual refresh; this
 * page is a historical/point-in-time report over an explicit date range
 * the admin picked, so a stale background number isn't the same kind of
 * problem -- React Query still refetches on window refocus/reconnect by
 * default, and changing the date range itself always issues a fresh fetch
 * since it's part of the query key). */
export function usePortalReportAnalytics(dateFrom: string, dateTo: string) {
  const router = useRouter();
  const session = useStaffSession();

  const {
    data,
    error: queryError,
    isFetching,
  } = useQuery({
    queryKey: ["portal-report-analytics", dateFrom, dateTo],
    queryFn: async () => {
      const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
      const result = await portalFetch(`/api/portal/report-analytics?${params.toString()}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return result.data as ReportAnalyticsData;
    },
  });

  return {
    data: data ?? null,
    error: queryError ? (queryError as Error).message : null,
    isFetching,
    hospital: session?.hospital ?? null,
  };
}
