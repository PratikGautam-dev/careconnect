import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";

export type Appointment = {
  id: number;
  phone: string;
  scheduled_at: string;
  status: string;
  appointment_type_id: string | null;
  video_link: string | null;
};

/** Item 4 (Spec.md Section 0): loads a specific doctor's own appointments
 * for today, within the existing shared staff portal -- no separate doctor
 * login exists, so this is just a scoped view any staff member can open. */
export function useDoctorTodayAppointments(doctorId: string) {
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/appointments/today`);
    if (result.ok) setAppointments((result.data as { appointments: Appointment[] }).appointments);
  }, [doctorId]);

  useEffect(() => {
    load();
  }, [load]);

  return { appointments };
}
