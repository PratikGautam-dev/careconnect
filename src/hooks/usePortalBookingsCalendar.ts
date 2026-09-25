import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";

export type CalendarAppointment = {
  id: number;
  phone: string;
  patient_name: string | null;
  patient_display_id: string | null;
  doctor_name: string | null;
  department_name: string | null;
  scheduled_at: string;
  status: string;
};

/** Loads GET /api/portal/bookings/calendar for the given month (+ optional
 * category scope) -- same portalFetch/useQuery pattern usePortalDashboard.ts
 * already established. `year`/`month`/`category` are all part of the query
 * key, so navigating a month (or a different PortalMiniCalendar instance
 * scoped to a different category) refetches automatically. */
export function usePortalBookingsCalendar(
  year: number,
  month: number,
  category?: "doctor" | "diagnostic" | "daycare",
) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    isFetching,
  } = useQuery({
    queryKey: ["portal-bookings-calendar", year, month, category ?? null],
    queryFn: async () => {
      const params = new URLSearchParams({ year: String(year), month: String(month) });
      if (category) params.set("category", category);
      const result = await portalFetch(`/api/portal/bookings/calendar?${params.toString()}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return (result.data as { appointments: CalendarAppointment[] }).appointments;
    },
  });

  return {
    // Cleared to null while (re)loading, same as the original load()
    // setting appointments to null before fetching.
    appointments: isFetching ? null : (data ?? null),
    error: queryError ? (queryError as Error).message : null,
  };
}
