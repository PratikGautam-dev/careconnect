import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchSlotsByDate } from "@/hooks/useAppointments";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import { newDaycareBookingSchema } from "@/lib/validation/newDaycareBooking";

export type Procedure = {
  id: number;
  name: string;
  category: string;
  booking_mode: "instant" | "approval_required";
  duration_minutes: number;
  estimated_price_min: number | null;
  estimated_price_max: number | null;
};
export type NewDaycareBookingContext = { procedures: Procedure[] };

/** Daycare/Procedure sibling of useNewTestBooking.ts -- same "context loads
 * only while open, every field resets on close" lifecycle, own
 * /api/portal/new-daycare-booking/context data source (the active procedure
 * catalog) and posting to /api/portal/new-daycare-booking.
 *
 * Unlike a test/lab booking, a procedure's own booking_mode decides whether
 * a slot is even picked here at all: "instant" fetches slots the same way
 * useNewTestBooking does (lazily, off the picked procedure, via
 * fetchSlotsByDate); "approval_required" skips the date/slot step
 * entirely -- submitting creates a bare request (procedure_status
 * REQUESTED) that shows up in the Daycare appointments page's own approval
 * queue, and a slot only gets picked later, after staff approves it. */
export function useNewDaycareBooking(
  open: boolean,
  onBooked?: () => void,
  initialPatientName?: string,
  initialPatientPhone?: string,
) {
  const router = useRouter();

  const { data: ctx, error: queryError } = useQuery({
    queryKey: ["portal-new-daycare-booking-context"],
    enabled: open,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/new-daycare-booking/context");
      return unwrapPortalResult<NewDaycareBookingContext>(router, result);
    },
  });

  const [errors, setErrors] = useState<string[]>([]);
  const [success, setSuccess] = useState(false);
  const [procedureStatus, setProcedureStatus] = useState<string | null>(null);

  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [patientDateOfBirth, setPatientDateOfBirth] = useState("");
  const [patientGender, setPatientGender] = useState("");
  const [procedureId, setProcedureIdRaw] = useState<number | null>(null);
  const [date, setDateRaw] = useState("");
  const [slotId, setSlotId] = useState("");

  // Open/close is seeded/reset during render (not an effect) -- React's own
  // "adjusting state when a prop changes" pattern -- so reopening always
  // starts from a clean form without costing an extra render cycle.
  const [seededOpen, setSeededOpen] = useState(false);
  if (open && !seededOpen) {
    setSeededOpen(true);
    setPatientName(initialPatientName ?? "");
    setPatientPhone(initialPatientPhone ?? "");
  } else if (!open && seededOpen) {
    setSeededOpen(false);
    setErrors([]);
    setSuccess(false);
    setProcedureStatus(null);
    setPatientName("");
    setPatientPhone("");
    setPatientDateOfBirth("");
    setPatientGender("");
    setProcedureIdRaw(null);
    setDateRaw("");
    setSlotId("");
  }

  const procedure = useMemo(
    () => ctx?.procedures.find((p) => p.id === procedureId) ?? null,
    [ctx, procedureId],
  );
  const isInstant = procedure?.booking_mode === "instant";

  function setProcedureId(id: number) {
    setProcedureIdRaw(id);
    setDateRaw("");
    setSlotId("");
  }

  const { data: slotsByDate } = useQuery({
    queryKey: ["portal-new-daycare-booking-slots", procedureId],
    enabled: isInstant && procedureId != null,
    retry: false,
    queryFn: async () => {
      const slots = await fetchSlotsByDate(router, { procedureId: String(procedureId) });
      return slots ?? {};
    },
  });

  function setDate(d: string) {
    setDateRaw(d);
    setSlotId("");
  }

  const datesForProcedure = slotsByDate ? Object.keys(slotsByDate).sort() : [];
  const slotsForDate = date && slotsByDate ? slotsByDate[date] || [] : [];

  const submitMutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const result = await portalFetch("/api/portal/new-daycare-booking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<{ errors?: string[]; procedure_status?: string }>(router, result);
    },
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors([]);

    const parsed = newDaycareBookingSchema.safeParse({
      patient_name: patientName,
      patient_phone: patientPhone,
      patient_date_of_birth: patientDateOfBirth,
      patient_gender: patientGender,
      procedure_id: procedureId,
      booking_mode: procedure?.booking_mode ?? "approval_required",
      slot_id: isInstant ? slotId : undefined,
    });
    if (!parsed.success) {
      setErrors(parsed.error.issues.map((issue) => issue.message));
      return;
    }

    try {
      const data = await submitMutation.mutateAsync({
        patient_name: parsed.data.patient_name,
        patient_phone: parsed.data.patient_phone,
        patient_date_of_birth: parsed.data.patient_date_of_birth,
        patient_gender: parsed.data.patient_gender,
        procedure_id: parsed.data.procedure_id,
        slot_id: parsed.data.slot_id || "",
      });
      if (data.errors?.length) {
        setErrors(data.errors);
        toast.error("Couldn't create booking", data.errors[0]);
        return;
      }
      toast.success(
        data.procedure_status === "CONFIRMED" ? "Booking confirmed" : "Request submitted",
      );
      setProcedureStatus(data.procedure_status ?? null);
      setSuccess(true);
      onBooked?.();
    } catch (err) {
      if (isPortalMutationError(err)) {
        setErrors([err.message]);
        toast.error("Couldn't create booking", err.message);
      }
    }
  }

  return {
    ctx: ctx ?? null,
    error: queryError ? "Couldn't load booking context — try again." : null,
    errors,
    submitting: submitMutation.isPending,
    success,
    procedureStatus,
    patientName,
    setPatientName,
    patientPhone,
    setPatientPhone,
    patientDateOfBirth,
    setPatientDateOfBirth,
    patientGender,
    setPatientGender,
    procedure,
    procedureId,
    setProcedureId,
    date,
    setDate,
    slotId,
    setSlotId,
    datesForProcedure,
    slotsForDate,
    slotsLoading: isInstant && procedureId != null && slotsByDate === undefined,
    handleSubmit,
  };
}
