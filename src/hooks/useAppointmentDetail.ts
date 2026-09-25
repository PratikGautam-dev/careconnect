import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import type { Appointment } from "@/hooks/useAppointments";

export type AppointmentPatient = {
  id: number;
  patient_display_id: string | null;
  mrn: string | null;
  date_of_birth: string | null;
  gender: string | null;
};

export type VisitNote = {
  id: number;
  note_text: string;
  created_at: string;
  doctor_name: string | null;
};

type AppointmentDetailResponse = {
  appointment: Appointment;
  patient: AppointmentPatient | null;
  notes: VisitNote[];
};

function detailQueryKey(appointmentId: string) {
  return ["portal-appointment-detail", appointmentId] as const;
}

/** Loads a single appointment (+ its patient + visit notes) for
 * /portal/appointments/[id]. Mutations (attendance, delete, add-note) live
 * in their own hooks below -- call this hook's `refetch` after one succeeds
 * to pick up the change. */
export function useAppointmentDetail(appointmentId: string, ready: boolean) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: detailQueryKey(appointmentId),
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/bookings/${appointmentId}`);
      return unwrapPortalResult<AppointmentDetailResponse>(router, result);
    },
  });

  return {
    appointment: data?.appointment ?? null,
    patient: data?.patient ?? null,
    notes: data?.notes ?? [],
    error: queryError ? "Couldn't load appointment — try again." : null,
    refetch,
  };
}

/** POST /api/portal/bookings/{id}/attendance -- mark attended/no-show from
 * the detail page. Caller should refetch useAppointmentDetail() on success. */
export function useMarkAppointmentAttendance() {
  const router = useRouter();

  return useMutation({
    mutationFn: async ({
      appointmentId,
      attended,
    }: {
      appointmentId: string;
      attended: boolean;
    }) => {
      const result = await portalFetch(`/api/portal/bookings/${appointmentId}/attendance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attended }),
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });
}

/** POST /api/portal/bookings/{id}/delete -- resolved-rows-only delete from
 * the detail page, then navigates back to the list. */
export function useDeleteAppointmentDetail() {
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: async (appointmentId: string) => {
      const result = await portalFetch(`/api/portal/bookings/${appointmentId}/delete`, {
        method: "POST",
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  async function deleteAndRedirect(appointmentId: string) {
    try {
      await mutation.mutateAsync(appointmentId);
      toast.success("Appointment deleted");
      router.push("/portal/appointments");
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't delete appointment", err.message);
    }
  }

  return { deleteAndRedirect, deleting: mutation.isPending };
}

/** POST /api/portal/bookings/{id}/collect-cash -- front-desk confirms cash
 * was actually collected (the "Record Payment" action on the appointment
 * detail page). Caller should refetch useAppointmentDetail() on success. */
export function useCollectCashPayment() {
  return useMutation({
    mutationFn: async ({
      appointmentId,
      amount,
      reference,
    }: {
      appointmentId: string;
      amount: number;
      reference: string;
    }) => {
      const result = await portalFetch(`/api/portal/bookings/${appointmentId}/collect-cash`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount, reference: reference.trim() || undefined }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });
}

/** POST /api/portal/patients/{patientId}/notes -- same patient-scoped note
 * system the patient record page already uses, not a separate appointment-
 * scoped note system. Caller should refetch useAppointmentDetail() on
 * success (the new note only shows up there). */
export function useAddVisitNote() {
  return useMutation({
    mutationFn: async ({ patientId, noteText }: { patientId: number; noteText: string }) => {
      const result = await portalFetch(`/api/portal/patients/${patientId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note_text: noteText }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });
}
