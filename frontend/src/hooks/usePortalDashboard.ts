import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getPortalHospital, portalFetch, type PortalHospital } from "@/lib/portalAuth";

export type DashboardData = {
  hospital: PortalHospital;
  stats: {
    today_appointments: number;
    today_appointments_delta_pct: number | null;
    confirmed_today: number;
    confirmed_today_delta_pct: number | null;
    new_patients_today: number;
    new_patients_today_delta_pct: number | null;
    no_shows_today: number;
    no_shows_today_delta_pct: number | null;
    upcoming_appointments: number;
  };
  weekly_counts: { date: string; label: string; count: number }[];
  department_breakdown: { department_name: string; count: number }[];
  recent_appointments: {
    id: number;
    phone: string;
    patient_name: string | null;
    patient_display_id: string | null;
    department_name: string;
    doctor_name: string;
    scheduled_at: string;
    status: string;
    source: string;
    reference_id: string | null;
  }[];
};

// New bookings (WhatsApp or staff-created) don't push to this tab -- there's
// no websocket/SSE infra in this app -- so poll instead of fetching once on
// mount, otherwise the numbers only ever update on a manual page reload.
const POLL_INTERVAL_MS = 20_000;

/** Loads + polls the /portal/dashboard stats. */
export function usePortalDashboard() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hospital, setHospital] = useState<PortalHospital | null>(null);
  const routerRef = useRef(router);
  routerRef.current = router;

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/dashboard");
    if (!result.ok) {
      if (result.unauthorized) routerRef.current.push("/portal/login");
      else setError(result.error);
      return;
    }
    setData(result.data as DashboardData);
  }, []);

  useEffect(() => {
    setHospital(getPortalHospital());
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  return { data, error, hospital };
}
