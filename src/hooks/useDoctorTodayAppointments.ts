import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";

export type Appointment = {
  id: number;
  phone: string;
  scheduled_at: string;
  status: string;
  appointment_type_id: string | null;
  video_link: string | null;
};

/** Loads a specific doctor's own appointments for today, within the shared
 * staff portal -- no separate doctor login exists, so this is just a
 * scoped view any staff member can open. */
export function useDoctorTodayAppointments(doctorId: string) {
  const { data: appointments } = useQuery({
    queryKey: ["portal-doctor-today-appointments", doctorId],
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/doctors/${doctorId}/appointments/today`);
      if (!result.ok) return null;
      return (result.data as { appointments: Appointment[] }).appointments;
    },
  });

  return { appointments: appointments ?? null };
}
