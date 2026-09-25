import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";

export type DoctorSchedule = {
  id: string;
  name: string;
  specialization: string | null;
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  slot_duration_minutes: number;
  effective_from: string | null;
};

export type LeaveEntry = { id: number; date: string; reason: string | null };

export type ScheduleAppointment = {
  id: number;
  phone: string;
  patient_display_id: string | null;
  department_name: string;
  scheduled_at: string;
  status: string;
  appointment_type_id: string | null;
  video_link: string | null;
};

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Loads everything DoctorScheduleView needs: this doctor's own schedule
 * (working days/hours/breaks + leave), today's appointments (for the
 * header tiles + "Today's schedule" panel, fetched independently of the
 * week grid so navigating weeks never changes what "today" means up top),
 * and the selected week's appointments -- three independent GETs, same
 * portalFetch/useQuery pattern usePortalDashboard.ts already established.
 * `weekStartKey` is part of the week query's own queryKey, so navigating
 * the week grid refetches automatically. */
export function useDoctorSchedule(weekStartKey: string) {
  const router = useRouter();

  const scheduleQuery = useQuery({
    queryKey: ["doctor-schedule"],
    queryFn: async () => {
      const result = await staffFetch("/api/doctor/schedule");
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return result.data as { doctor: DoctorSchedule; leave: LeaveEntry[] };
    },
  });

  // No error surfaced on failure here (beyond the unauthorized redirect) --
  // matches the original loadToday()'s own silent-failure contract; only
  // loadSchedule/loadWeek ever set the page-level error banner.
  const todayQuery = useQuery({
    queryKey: ["doctor-schedule-today"],
    queryFn: async () => {
      const result = await staffFetch("/api/doctor/appointments/week");
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        return [] as ScheduleAppointment[];
      }
      const todayKey = dateKey(new Date());
      const all = (result.data as { appointments: ScheduleAppointment[] }).appointments;
      return all.filter((a) => dateKey(new Date(a.scheduled_at)) === todayKey);
    },
  });

  const weekQuery = useQuery({
    queryKey: ["doctor-schedule-week", weekStartKey],
    queryFn: async () => {
      const result = await staffFetch(`/api/doctor/appointments/week?start=${weekStartKey}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return (result.data as { appointments: ScheduleAppointment[] }).appointments;
    },
  });

  const error =
    (scheduleQuery.error as Error | null)?.message ||
    (weekQuery.error as Error | null)?.message ||
    null;

  return {
    schedule: scheduleQuery.data?.doctor ?? null,
    leave: scheduleQuery.data?.leave ?? null,
    // Cleared to null while (re)loading, same as the original loadToday()/
    // loadWeek() setting their own state to null before fetching.
    todayAppointments: todayQuery.isFetching ? null : (todayQuery.data ?? null),
    weekAppointments: weekQuery.isFetching || weekQuery.isError ? null : (weekQuery.data ?? null),
    error,
    refetchSchedule: scheduleQuery.refetch,
  };
}
