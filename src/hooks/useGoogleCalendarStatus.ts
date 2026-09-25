import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";

export type CalendarStatus = {
  configured: boolean;
  connected: boolean;
  google_email: string | null;
};

/** Loads the hospital's Google Calendar connection status for
 * GoogleCalendarCard -- same staffFetch + useQuery pattern usePortalDashboard.ts
 * already established. Resolves to `null` on failure rather than throwing
 * (same fire-and-forget-on-failure contract the original inline fetch had:
 * there's no dedicated error state for this card, the UI just keeps
 * showing "Loading…" instead of surfacing an error). */
export function useGoogleCalendarStatus() {
  const { data, refetch } = useQuery({
    queryKey: ["portal-google-calendar-status"],
    queryFn: async () => {
      const result = await staffFetch("/api/portal/calendar/status");
      return result.ok ? (result.data as CalendarStatus) : null;
    },
  });

  return { status: data ?? null, refetch };
}
