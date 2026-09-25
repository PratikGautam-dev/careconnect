import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";

export type DoctorDashboardAppointment = {
  id: number;
  phone: string;
  patient_display_id: string | null;
  department_name: string;
  scheduled_at: string;
  status: string;
  reference_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
};

export type DoctorDashboardInsights = {
  new_patients_this_week: number;
  new_patients_this_week_delta_pct: number | null;
  follow_ups_this_week: number;
  follow_ups_this_week_delta_pct: number | null;
  // No prescriptions table or consult-duration capture anywhere in this
  // app yet -- null renders as "—" rather than a made-up number (see
  // get_doctor_patient_insights()'s own docstring on the backend).
  prescriptions_issued_this_week: number | null;
  avg_consult_minutes: number | null;
};

export type DoctorDashboardData = {
  stats: {
    today_appointments: number;
    confirmed_today: number;
    attended_today: number;
    no_shows_today: number;
    upcoming_appointments: number;
  };
  today_appointments: DoctorDashboardAppointment[];
  weekly_counts: { date: string; label: string; count: number }[];
  insights: DoctorDashboardInsights;
};

// Same reasoning as usePortalDashboard's own polling -- no websocket/SSE
// infra, so a doctor's numbers only update on a manual refresh otherwise.
const POLL_INTERVAL_MS = 20_000;

/** Loads + polls GET /api/doctor/dashboard for DoctorDashboardView --
 * same portalFetch/useQuery + refetchInterval pattern usePortalDashboard.ts
 * already established, just staffFetch-backed (this doctor's own session)
 * instead of the hospital-wide portalFetch. */
export function useDoctorDashboard() {
  const router = useRouter();

  const {
    data,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["doctor-dashboard"],
    refetchInterval: POLL_INTERVAL_MS,
    queryFn: async () => {
      const result = await staffFetch("/api/doctor/dashboard");
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return result.data as DoctorDashboardData;
    },
  });

  return {
    data: data ?? null,
    error: queryError ? (queryError as Error).message : null,
    refetch,
  };
}
