import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

// Matches admin/dashboard_api.py's GET /api/admin/dashboard ->
// db.get_hospital_dashboard_stats() (db/repositories/hospitals.py). Every
// field here is backed by a real table -- there's no subscription/plan/
// billing/support-ticket model in this codebase yet, so those cards are
// rendered from hardcoded mock data in the page itself, not this hook.
export type HospitalStats = {
  total: number;
  active: number;
  inactive: number;
  new_this_month: number;
  by_tier: Record<string, number>;
  growth_trend: { month: string; total_hospitals: number }[];
};

export type RecentActivity = {
  id: number;
  actor_level: string;
  hospital_id: number | null;
  hospital_name: string | null;
  actor_label: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
};

export type SuperAdminDashboard = {
  hospitals: HospitalStats;
  total_bookings: number;
  recent_activity: RecentActivity[];
};

/** Real, DB-backed stats for the /admin/dashboard overview -- GET
 * /api/admin/dashboard. */
export function useSuperAdminDashboard() {
  const {
    data,
    error: queryError,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["super-admin-dashboard"],
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/dashboard");
      return unwrapAdminResult<SuperAdminDashboard>(result);
    },
  });

  return {
    dashboard: data ?? null,
    error: queryError ? (queryError as Error).message : null,
    isFetching,
    load: refetch,
  };
}
