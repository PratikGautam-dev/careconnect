import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";

export type Department = { id: string; name: string };
export type Doctor = { id: string; name: string };
export type Slot = { id: string; label: string };
export type NewBookingContext = {
  departments: Department[];
  doctors_by_department: Record<string, Doctor[]>;
  slots_by_doctor: Record<string, Record<string, Slot[]>>;
};

/** Loads department/doctor/slot context + submits the /portal/new-booking
 * staff-created booking form. */
export function useNewBooking(ready: boolean) {
  const router = useRouter();
  const [ctx, setCtx] = useState<NewBookingContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [departmentId, setDepartmentIdRaw] = useState("");
  const [doctorId, setDoctorIdRaw] = useState("");
  const [date, setDateRaw] = useState("");
  const [slotId, setSlotId] = useState("");

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/new-booking/context");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setCtx(result.data as NewBookingContext);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

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
  const datesForDoctor = doctorId && ctx ? Object.keys(ctx.slots_by_doctor[doctorId] || {}).sort() : [];
  const slotsForDate = doctorId && date && ctx ? ctx.slots_by_doctor[doctorId]?.[date] || [] : [];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErrors([]);
    const result = await portalFetch("/api/portal/new-booking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patient_name: patientName, patient_phone: patientPhone,
        department_id: departmentId, doctor_id: doctorId, slot_id: slotId,
      }),
    });
    setSubmitting(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setErrors([result.error]);
      return;
    }
    const data = result.data as { errors?: string[] };
    if (data.errors?.length) {
      setErrors(data.errors);
      return;
    }
    setSuccess(true);
  }

  return {
    ctx, error, errors, submitting, success,
    patientName, setPatientName, patientPhone, setPatientPhone,
    departmentId, setDepartmentId, doctorId, setDoctorId, date, setDate, slotId, setSlotId,
    doctors, datesForDoctor, slotsForDate,
    handleSubmit,
  };
}
