import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

const DEFAULT_CANCEL_MESSAGE = "Your appointment has been cancelled.";
const DEFAULT_RESCHEDULE_MESSAGE = "Your appointment has been rescheduled.";

export type Appointment = {
  id: number;
  phone: string;
  department_name: string;
  doctor_name: string;
  scheduled_at: string;
  status: string;
  source: string;
  reference_id: string | null;
  patient_display_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
  created_at: string | null;
  // Lab Test Phase 2 follow-up: null for every non-Lab-Test appointment.
  lab_status: string | null;
  // Daycare/Procedure rebuild: null for every non-procedure appointment.
  // scheduled_at above is a PLACEHOLDER (request creation time) until
  // procedure_status reaches "CONFIRMED" -- don't display it as a real
  // slot before then.
  procedure_id: number | null;
  procedure_name: string | null;
  procedure_status: string | null;
  procedure_estimated_price_min: number | null;
  procedure_estimated_price_max: number | null;
  procedure_order_reference: string | null;
  procedure_reschedule_requested_at: string | null;
};

export type Department = { id: string; name: string };
export type Doctor = { id: string; name: string };
export type Slot = { id: string; label: string };
export type NewBookingContext = {
  departments: Department[];
  doctors_by_department: Record<string, Doctor[]>;
  slots_by_doctor: Record<string, Record<string, Slot[]>>;
};

// docs/per-appointment-type-flow-plan.md's fixed catalog (db/repositories/
// appointment_types.py's DEFAULT_APPOINTMENT_TYPES) -- there's no portal CRUD
// for appointment types (seeded once, at onboarding), so this mirrors that
// same fixed id->label mapping rather than fetching it from a new endpoint.
export const TYPE_LABELS: Record<string, string> = {
  new: "New Consultation",
  followup: "Follow-up",
  tele: "Tele-consultation",
  second_opinion: "Second Opinion",
  diagnostic: "Diagnostic",
  lab: "Lab Test",
  daycare: "Daycare",
};

function typeBucket(a: Appointment) {
  return a.appointment_type_id && a.appointment_type_id in TYPE_LABELS ? a.appointment_type_id : "other";
}

/** Loads + owns every mutation on the /portal/appointments list -- cancel,
 * reschedule, attendance marking, delete -- plus the search/status/type
 * filters and the cancel/reschedule inline panels' own form state. */
export function useAppointments(ready: boolean) {
  const router = useRouter();
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [cancelPanelId, setCancelPanelId] = useState<number | null>(null);
  const [cancelMessage, setCancelMessage] = useState(DEFAULT_CANCEL_MESSAGE);

  const [reschedulePanelId, setReschedulePanelId] = useState<number | null>(null);
  const [reschedulingId, setReschedulingId] = useState<number | null>(null);
  const [rescheduleCtx, setRescheduleCtx] = useState<NewBookingContext | null>(null);
  const [rescheduleErrors, setRescheduleErrors] = useState<string[]>([]);
  const [rescheduleMessage, setRescheduleMessage] = useState(DEFAULT_RESCHEDULE_MESSAGE);
  const [rDepartmentId, setRDepartmentId] = useState("");
  const [rDoctorId, setRDoctorId] = useState("");
  const [rDate, setRDate] = useState("");
  const [rSlotId, setRSlotId] = useState("");
  const [markingAttendanceId, setMarkingAttendanceId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<Appointment[] | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Item 2 (Spec.md Section 0): search (patient phone / doctor / department
  // name) + status filter -- computed client-side, same reasoning the
  // doctors page uses (this list is already bounded to 500 rows by the
  // backend, small enough that a server round-trip per keystroke isn't
  // needed).
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  // Divides the appointments list by type (New Consultation, Follow-up,
  // Tele-consultation, ...) as its own tab row -- "other" covers any
  // appointment predating appointment_type_id (never backfilled, so an
  // old row is legitimately typeless, not a bug).
  const [typeFilter, setTypeFilter] = useState("all");

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/bookings");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setAppointments((result.data as { appointments: Appointment[] }).appointments);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  // Shared success/error-toast handling for the many fire-and-forget row
  // actions below (attendance, lab status, procedure actions, delete) --
  // every one of them used to just no-op on failure with zero feedback.
  function afterAction(result: Awaited<ReturnType<typeof portalFetch>>, successMessage: string, failureMessage: string): boolean {
    if (result.ok) {
      toast.success(successMessage);
      return true;
    }
    if (result.unauthorized) {
      router.push("/portal/login");
      return false;
    }
    toast.error(failureMessage, result.error);
    return false;
  }

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: appointments?.length ?? 0 };
    for (const a of appointments || []) {
      const bucket = typeBucket(a);
      counts[bucket] = (counts[bucket] || 0) + 1;
    }
    return counts;
  }, [appointments]);

  const filteredAppointments = useMemo(() => {
    if (!appointments) return appointments;
    const q = searchQuery.trim().toLowerCase();
    return appointments.filter((a) => {
      if (typeFilter !== "all" && typeBucket(a) !== typeFilter) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (!q) return true;
      return (
        a.phone.toLowerCase().includes(q) ||
        a.doctor_name.toLowerCase().includes(q) ||
        a.department_name.toLowerCase().includes(q) ||
        (a.reference_id || "").toLowerCase().includes(q) ||
        (a.patient_display_id || "").toLowerCase().includes(q)
      );
    });
  }, [appointments, searchQuery, statusFilter, typeFilter]);

  // Item 9 (Spec.md Section 0): closes the "no-shows are a heuristic, not a
  // real status" gap -- a still-'booked' appointment whose scheduled time
  // has already passed gets an inline "Did the patient visit?" prompt,
  // computed from fields the list already has (no separate fetch needed).
  async function handleAttendance(id: number, attended: boolean) {
    setMarkingAttendanceId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/attendance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attended }),
    });
    setMarkingAttendanceId(null);
    if (afterAction(result, attended ? "Marked as attended" : "Marked as no-show", "Couldn't update attendance")) load();
  }

  // Lab Test Phase 2 follow-up: advances booked -> sample_collected ->
  // processing one step at a time -- report_ready is never set from here,
  // only automatically, by uploading a lab_report document against the
  // appointment (the Patients page's document upload, not this list).
  const [advancingLabStatusId, setAdvancingLabStatusId] = useState<number | null>(null);
  async function handleAdvanceLabStatus(id: number) {
    setAdvancingLabStatusId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/lab-status`, { method: "POST" });
    setAdvancingLabStatusId(null);
    if (afterAction(result, "Lab status updated", "Couldn't update lab status")) load();
  }

  // Daycare/Procedure rebuild: approve/reject a pending request, or advance
  // an already-CONFIRMED procedure's status (CONFIRMED -> COMPLETED, or ->
  // CANCELLED) -- same "one action in flight per row" shape as the lab-status
  // advance above.
  const [procedureActionId, setProcedureActionId] = useState<number | null>(null);
  async function handleApproveProcedureRequest(id: number) {
    setProcedureActionId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/procedure/approve`, { method: "POST" });
    setProcedureActionId(null);
    if (result.ok) load();
  }
  async function handleRejectProcedureRequest(id: number, reason?: string) {
    setProcedureActionId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/procedure/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason || "" }),
    });
    setProcedureActionId(null);
    if (result.ok) load();
  }
  async function handleAdvanceProcedureStatus(id: number) {
    setProcedureActionId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/procedure/advance-status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    setProcedureActionId(null);
    if (result.ok) load();
  }
  async function handleApproveProcedureReschedule(id: number) {
    setProcedureActionId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/procedure/reschedule-request/approve`, { method: "POST" });
    setProcedureActionId(null);
    if (result.ok) load();
  }
  async function handleRejectProcedureReschedule(id: number) {
    setProcedureActionId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/procedure/reschedule-request/reject`, { method: "POST" });
    setProcedureActionId(null);
    if (result.ok) load();
  }

  // Item 3 (Spec.md Section 0): soft-delete only, per this project's
  // never-hard-delete convention -- restricted server-side to non-'booked'
  // rows (cancel it first), same guard reflected here by only offering the
  // button once status !== "booked".
  async function handleDelete(id: number) {
    if (!window.confirm("Delete this appointment record? This can't be undone from the portal.")) return;
    setDeletingId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/delete`, { method: "POST" });
    setDeletingId(null);
    if (result.ok) load();
  }

  // Bulk select + delete, same shape as usePatients' row checkboxes + "Delete
  // selected" action -- restricted to non-'booked' rows since that's the same
  // guard the single-row delete button (and the backend) already enforces;
  // a 'booked' appointment can't be selected at all rather than silently
  // failing once "Delete selected" is clicked.
  const toggleSelected = (id: number, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const deletableAppointments = (filteredAppointments ?? appointments ?? []).filter((a) => a.status !== "booked");

  const toggleSelectAll = (checked: boolean) => {
    setSelected(checked ? new Set(deletableAppointments.map((a) => a.id)) : new Set());
  };

  const runBulkDelete = async (targets: Appointment[]) => {
    setBulkDeleting(true);
    const result = await portalFetch("/api/portal/bookings/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ appointment_ids: targets.map((a) => a.id) }),
    });
    setBulkDeleting(false);
    setPendingDelete(null);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const deletedIds = new Set((result.data as { deleted: number[] }).deleted);
    setAppointments((prev) => (prev ? prev.filter((a) => !deletedIds.has(a.id)) : prev));
    setSelected((prev) => {
      const next = new Set(prev);
      deletedIds.forEach((id) => next.delete(id));
      return next;
    });
  };

  function openCancelPanel(id: number) {
    setReschedulePanelId(null);
    setCancelPanelId(id);
    setCancelMessage(DEFAULT_CANCEL_MESSAGE);
  }

  function closeCancelPanel() {
    setCancelPanelId(null);
  }

  async function handleCancel(id: number) {
    setCancellingId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: cancelMessage.trim() }),
    });
    setCancellingId(null);
    setCancelPanelId(null);
    if (result.ok) load();
  }

  async function openReschedulePanel(id: number) {
    setCancelPanelId(null);
    setReschedulePanelId(id);
    setRescheduleMessage(DEFAULT_RESCHEDULE_MESSAGE);
    setRescheduleErrors([]);
    setRDepartmentId("");
    setRDoctorId("");
    setRDate("");
    setRSlotId("");
    if (!rescheduleCtx) {
      // Reuses the exact same context endpoint /portal/new-booking already
      // reads department/doctor/slot options from -- no separate endpoint,
      // and staff can pick a different doctor for the reschedule, not just
      // a different slot with the same one.
      const result = await portalFetch("/api/portal/new-booking/context");
      if (result.ok) setRescheduleCtx(result.data as NewBookingContext);
    }
  }

  function closeReschedulePanel() {
    setReschedulePanelId(null);
  }

  async function handleReschedule(id: number) {
    setReschedulingId(id);
    setRescheduleErrors([]);
    const result = await portalFetch(`/api/portal/bookings/${id}/reschedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        department_id: rDepartmentId, doctor_id: rDoctorId, slot_id: rSlotId,
        message: rescheduleMessage.trim(),
      }),
    });
    setReschedulingId(null);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setRescheduleErrors([result.error]);
      return;
    }
    const data = result.data as { errors?: string[] };
    if (data.errors?.length) {
      setRescheduleErrors(data.errors);
      return;
    }
    setReschedulePanelId(null);
    load();
  }

  const rDoctors = rDepartmentId && rescheduleCtx ? rescheduleCtx.doctors_by_department[rDepartmentId] || [] : [];
  const rDatesForDoctor = rDoctorId && rescheduleCtx ? Object.keys(rescheduleCtx.slots_by_doctor[rDoctorId] || {}).sort() : [];
  const rSlotsForDate = rDoctorId && rDate && rescheduleCtx ? rescheduleCtx.slots_by_doctor[rDoctorId]?.[rDate] || [] : [];

  const selectedAppointments = deletableAppointments.filter((a) => selected.has(a.id));
  const allSelected = deletableAppointments.length > 0 && selected.size === deletableAppointments.length;

  return {
    appointments, error, filteredAppointments, typeCounts,
    searchQuery, setSearchQuery, statusFilter, setStatusFilter, typeFilter, setTypeFilter,
    cancellingId, cancelPanelId, cancelMessage, setCancelMessage, openCancelPanel, closeCancelPanel, handleCancel,
    reschedulePanelId, reschedulingId, rescheduleCtx, rescheduleErrors, rescheduleMessage, setRescheduleMessage,
    rDepartmentId, setRDepartmentId, rDoctorId, setRDoctorId, rDate, setRDate, rSlotId, setRSlotId,
    rDoctors, rDatesForDoctor, rSlotsForDate,
    openReschedulePanel, closeReschedulePanel, handleReschedule,
    markingAttendanceId, handleAttendance,
    advancingLabStatusId, handleAdvanceLabStatus,
    procedureActionId, handleApproveProcedureRequest, handleRejectProcedureRequest,
    handleAdvanceProcedureStatus, handleApproveProcedureReschedule, handleRejectProcedureReschedule,
    deletingId, handleDelete,
    selected, toggleSelected, toggleSelectAll, deletableAppointments, selectedAppointments, allSelected,
    pendingDelete, setPendingDelete, bulkDeleting, runBulkDelete,
  };
}
