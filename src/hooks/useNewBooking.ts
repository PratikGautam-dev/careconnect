import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchSlotsByDate, type SlotsByDate } from "@/hooks/useAppointments";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import { newBookingSchema } from "@/lib/validation/newBooking";

export type Department = { id: string; name: string };
export type Doctor = { id: string; name: string };
export type Slot = { id: string; label: string };
export type NewBookingContext = {
  departments: Department[];
  doctors_by_department: Record<string, Doctor[]>;
};

/** Loads department/doctor context + submits the New Booking dialog's form
 * -- context is only fetched while the dialog is open, and every field
 * resets the moment it closes, so reopening always starts from a clean
 * form rather than showing the last attempt's leftover values/errors.
 * Slots for the picked doctor are fetched separately, lazily, the moment
 * doctorId changes -- not eager-loaded for every doctor up front. */
export function useNewBooking(
  open: boolean,
  onBooked?: () => void,
  initialPatientName?: string,
  initialPatientPhone?: string,
) {
  const router = useRouter();

  const { data: ctx, error: queryError } = useQuery({
    queryKey: ["portal-new-booking-context"],
    enabled: open,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/new-booking/context");
      return unwrapPortalResult<NewBookingContext>(router, result);
    },
  });

  const [errors, setErrors] = useState<string[]>([]);
  const [success, setSuccess] = useState(false);

  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [patientDateOfBirth, setPatientDateOfBirth] = useState("");
  const [patientGender, setPatientGender] = useState("");
  const [departmentId, setDepartmentIdRaw] = useState("");
  const [doctorId, setDoctorIdRaw] = useState("");
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
    setPatientName("");
    setPatientPhone("");
    setPatientDateOfBirth("");
    setPatientGender("");
    setDepartmentIdRaw("");
    setDoctorIdRaw("");
    setDateRaw("");
    setSlotId("");
  }

  const { data: slotsByDate } = useQuery({
    queryKey: ["portal-new-booking-slots", doctorId],
    enabled: !!doctorId,
    retry: false,
    queryFn: async () => {
      const slots = await fetchSlotsByDate(router, { doctorId });
      return slots ?? {};
    },
  });

  function setDepartmentId(id: string) {
    setDepartmentIdRaw(id);
    setDoctorIdRaw("");
    setDateRaw("");
    setSlotId("");
  }

  function setDoctorId(id: string) {
    setDoctorIdRaw(id);
    setDateRaw("");
    setSlotId("");
  }

  function setDate(d: string) {
    setDateRaw(d);
    setSlotId("");
  }

  const doctors = departmentId && ctx ? ctx.doctors_by_department[departmentId] || [] : [];
  const datesForDoctor = slotsByDate ? Object.keys(slotsByDate).sort() : [];
  const slotsForDate: SlotsByDate[string] = date && slotsByDate ? slotsByDate[date] || [] : [];

  const submitMutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const result = await portalFetch("/api/portal/new-booking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<{ errors?: string[] }>(router, result);
    },
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors([]);

    // Client-side validation before ever hitting the API -- the backend
    // still re-validates everything itself (payload.errors below), this
    // just catches the obvious cases (empty phone, nothing picked yet)
    // without a round-trip.
    const parsed = newBookingSchema.safeParse({
      patient_name: patientName,
      patient_phone: patientPhone,
      patient_date_of_birth: patientDateOfBirth,
      patient_gender: patientGender,
      department_id: departmentId,
      doctor_id: doctorId,
      slot_id: slotId,
    });
    if (!parsed.success) {
      setErrors(parsed.error.issues.map((issue) => issue.message));
      return;
    }

    try {
      const data = await submitMutation.mutateAsync(parsed.data);
      if (data.errors?.length) {
        setErrors(data.errors);
        toast.error("Couldn't create booking", data.errors[0]);
        return;
      }
      toast.success("Booking created");
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
    patientName,
    setPatientName,
    patientPhone,
    setPatientPhone,
    patientDateOfBirth,
    setPatientDateOfBirth,
    patientGender,
    setPatientGender,
    departmentId,
    setDepartmentId,
    doctorId,
    setDoctorId,
    date,
    setDate,
    slotId,
    setSlotId,
    doctors,
    datesForDoctor,
    slotsForDate,
    // true while a doctor is picked but its slots haven't come back yet --
    // lets the dialog show "Loading…" instead of a misleading "No available
    // dates" during that gap.
    slotsLoading: !!doctorId && slotsByDate === undefined,
    handleSubmit,
  };
}
