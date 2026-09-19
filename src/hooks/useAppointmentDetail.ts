import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";
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

/** Loads a single appointment (+ its patient + visit notes) for
 * /portal/appointments/[id], and owns the detail page's own actions --
 * mark attendance, delete (resolved rows only, same as the list page), and
 * add a visit note (patient-scoped, same /api/portal/patients/{id}/notes
 * the patient record page already uses -- not a separate appointment-scoped
 * note system). Cancel/reschedule stay list-only for now (that flow's
 * inline department/doctor/date/slot context lives in useAppointments.ts). */
export function useAppointmentDetail(appointmentId: string, ready: boolean) {
  const router = useRouter();
  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const [patient, setPatient] = useState<AppointmentPatient | null>(null);
  const [notes, setNotes] = useState<VisitNote[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/bookings/${appointmentId}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { appointment: Appointment; patient: AppointmentPatient | null; notes: VisitNote[] };
    setAppointment(data.appointment);
    setPatient(data.patient);
    setNotes(data.notes);
  }, [appointmentId, router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleAttendance(attended: boolean) {
    setMarking(true);
    const result = await portalFetch(`/api/portal/bookings/${appointmentId}/attendance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attended }),
    });
    setMarking(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else toast.error("Couldn't update attendance", result.error);
      return;
    }
    load();
  }

  async function handleDelete() {
    setDeleting(true);
    const result = await portalFetch(`/api/portal/bookings/${appointmentId}/delete`, { method: "POST" });
    setDeleting(false);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else toast.error("Couldn't delete appointment", result.error);
      return;
    }
    toast.success("Appointment deleted");
    router.push("/portal/appointments");
  }

  async function handleAddNote() {
    if (!noteText.trim() || !patient) return;
    setSavingNote(true);
    setNoteError(null);
    const result = await portalFetch(`/api/portal/patients/${patient.id}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_text: noteText.trim() }),
    });
    setSavingNote(false);
    if (!result.ok) {
      setNoteError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNoteText("");
    load();
  }

  return {
    appointment, patient, notes, error, marking, deleting,
    handleAttendance, handleDelete,
    noteText, setNoteText, savingNote, noteError, handleAddNote,
  };
}
