import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";

export type DoctorCalendarAppointment = {
  id: number;
  phone: string;
  department_name: string;
  scheduled_at: string;
  status: string;
  patient_display_id: string | null;
};

/** Loads GET /api/doctor/appointments/calendar for the given month, for
 * AppointmentCalendar -- same staffFetch/useQuery pattern
 * usePortalDashboard.ts already established. `year`/`month` are part of
 * the query key, so navigating a month refetches automatically. */
export function useDoctorAppointmentsCalendar(year: number, month: number) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    isFetching,
  } = useQuery({
    queryKey: ["doctor-appointments-calendar", year, month],
    queryFn: async () => {
      const result = await staffFetch(
        `/api/doctor/appointments/calendar?year=${year}&month=${month}`,
      );
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return (result.data as { appointments: DoctorCalendarAppointment[] }).appointments;
    },
  });

  return {
    // Cleared to null while (re)loading, same as the original load()
    // setting appointments to null before fetching.
    appointments: isFetching ? null : (data ?? null),
    error: queryError ? (queryError as Error).message : null,
  };
}
