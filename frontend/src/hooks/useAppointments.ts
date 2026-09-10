import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

const PAGE_SIZE = 10;

const DEFAULT_CANCEL_MESSAGE = "Your appointment has been cancelled.";
const DEFAULT_RESCHEDULE_MESSAGE = "Your appointment has been rescheduled.";

export type Appointment = {
  id: number;
  phone: string;
  patient_name: string | null;
  department_id: string | null;
  department_name: string | null;
  doctor_id: string | null;
  doctor_name: string | null;
  // Diagnostic/Lab reschedule follow-up: set (doctor_id/doctor_name both
  // null) for a resource-bound booking -- an MRI machine or lab collection
  // point, not a doctor. Diagnostic tests/resources merge: this is a
  // diagnostic_tests.id now -- a test IS the schedulable resource.
  resource_id: number | null;
  resource_name: string | null;
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
export type Resource = { id: number; name: string };
export type Slot = { id: string; label: string };
export type NewBookingContext = {
  departments: Department[];
  doctors_by_department: Record<string, Doctor[]>;
  slots_by_doctor: Record<string, Record<string, Slot[]>>;
  // Diagnostic/Lab reschedule follow-up: the resource-bound equivalent of
  // doctors_by_department/slots_by_doctor above -- a resource has no
  // department picker of its own in this dialog, so just a flat list.
  resources: Resource[];
  slots_by_resource: Record<string, Record<string, Slot[]>>;
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

// Mirrors backend/db/repositories/appointment_types.py's
// BOOK_DOCTOR_APPOINTMENT_CATEGORY/TESTS_DIAGNOSTICS_CATEGORY -- the same
// 3-way split the WhatsApp booking menu and the portal sidebar (Doctor
// appointments / Diagnostic & lab / Report review) both use. Scoping by
// category now happens server-side (get_appointments_page's own `category`
// param) -- this type just labels which scope a page's hook call wants.
export type AppointmentCategory = "all" | "doctor" | "diagnostic";

// Shared vocabulary for every list page's tab pills (appointments/page.tsx's
// Today/Upcoming/Completed/Cancelled, diagnostic/page.tsx's own
// Diagnostics/Lab tests/Completed/Pending/Cancelled) -- each page still owns
// its own tab id/label list (they differ per page), it just needs to be
// drawn from this set so tabToServerParams below knows every id. Resolving
// a tab to server params (rather than filtering the loaded page client-side,
// like both pages used to) is what keeps a tab pill meaning "every matching
// row", not just whichever ones landed on the current 10-row page.
export type AppointmentTab = "all" | "today" | "upcoming" | "completed" | "cancelled" | "pending" | "diagnostics" | "lab";

function tabToServerParams(tab: string): { status?: string; type?: string; when?: string } {
  switch (tab as AppointmentTab) {
    case "today": return { when: "today" };
    case "upcoming": return { when: "upcoming" };
    case "completed": return { status: "attended" };
    case "cancelled": return { status: "cancelled" };
    case "pending": return { status: "booked" };
    case "diagnostics": return { type: "diagnostic" };
    case "lab": return { type: "lab" };
    default: return {};
  }
}

/** Loads + owns every mutation on the /portal/appointments list -- cancel,
 * reschedule, attendance marking, delete -- plus the search/status/type
 * filters, pagination, and the cancel/reschedule inline panels' own form
 * state. `category` scopes the loaded list itself (not just a tab filter)
 * -- "doctor" for the Doctor appointments page, "diagnostic" for the
 * Diagnostic & lab test page, "all" (default) elsewhere. `tab` is the
 * calling page's own current tab pill id (see AppointmentTab) -- passed in
 * rather than owned here since each page's tab labels/ids differ; this
 * hook only needs the id to resolve it to server params. */
export function useAppointments(ready: boolean, category: AppointmentCategory = "all", tab: string = "all") {
  const router = useRouter();
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [cancelPanelId, setCancelPanelId] = useState<number | null>(null);
  const [cancelMessage, setCancelMessage] = useState(DEFAULT_CANCEL_MESSAGE);

  const [reschedulePanelId, setReschedulePanelId] = useState<number | null>(null);
  const [reschedulingId, setReschedulingId] = useState<number | null>(null);
  const [rescheduleCtx, setRescheduleCtx] = useState<NewBookingContext | null>(null);
  const [rescheduleErrors, setRescheduleErrors] = useState<string[]>([]);
  const [rescheduleMessage, setRescheduleMessage] = useState(DEFAULT_RESCHEDULE_MESSAGE);
  // Department/doctor (or resource) are fixed to whichever the appointment
  // already has -- rescheduling only moves the date/slot, so this is set
  // once (from the appointment being rescheduled) when the dialog opens,
  // never from a user pick. Kept internal (not returned below) since
  // RescheduleDialog reads department_name/doctor_name/resource_name
  // straight off the Appointment it's given for display -- these are only
  // here to index into rescheduleCtx.slots_by_doctor/slots_by_resource.
  const [rDoctorId, setRDoctorId] = useState("");
  const [rResourceId, setRResourceId] = useState("");
  const [rDate, setRDate] = useState("");
  const [rSlotId, setRSlotId] = useState("");
  const [markingAttendanceId, setMarkingAttendanceId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<Appointment[] | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const [page, setPage] = useState(1);

  // "Draft" values -- what the search box/FilterSelect dropdowns show and
  // update live as the user types/picks. Nothing is sent to the server
  // until applyFilters() runs (the Filter button); resetFilters() clears
  // both draft and applied. Same staged-then-Apply pattern sarvaya-
  // dashboard's own filter bars (ExpenseFilterBar etc.) use -- a network
  // request per keystroke isn't wanted now that search hits the backend.
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [appliedStatus, setAppliedStatus] = useState("all");
  const [appliedType, setAppliedType] = useState("all");

  const applyFilters = useCallback(() => {
    setAppliedSearch(searchQuery.trim());
    setAppliedStatus(statusFilter);
    setAppliedType(typeFilter);
    setPage(1);
  }, [searchQuery, statusFilter, typeFilter]);

  const resetFilters = useCallback(() => {
    setSearchQuery("");
    setStatusFilter("all");
    setTypeFilter("all");
    setAppliedSearch("");
    setAppliedStatus("all");
    setAppliedType("all");
    setPage(1);
  }, []);

  const filtersDirty = searchQuery.trim() !== appliedSearch || statusFilter !== appliedStatus || typeFilter !== appliedType;

  // A tab pill switch changes which rows exist at all -- staying on page 3
  // of the old tab would otherwise render an empty table under the new one.
  // Reset during render (React's own "adjusting state when a prop changes"
  // pattern) rather than in an effect, which would cause an extra render.
  const [prevTab, setPrevTab] = useState(tab);
  if (tab !== prevTab) {
    setPrevTab(tab);
    setPage(1);
  }

  const queryKey = ["portal-bookings", category, page, appliedSearch, appliedStatus, appliedType, tab] as const;

  const {
    data, isFetching, error: queryError, refetch,
  } = useQuery({
    queryKey,
    enabled: ready,
    placeholderData: keepPreviousData,
    retry: false,
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), limit: String(PAGE_SIZE) });
      if (category !== "all") params.set("category", category);
      const tabParams = tabToServerParams(tab);
      const status = tabParams.status || (appliedStatus !== "all" ? appliedStatus : "");
      const type = tabParams.type || (appliedType !== "all" ? appliedType : "");
      if (status) params.set("status", status);
      if (type) params.set("type", type);
      if (tabParams.when) params.set("when", tabParams.when);
      if (appliedSearch) params.set("search", appliedSearch);
      const result = await portalFetch(`/api/portal/bookings?${params.toString()}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return result.data as { appointments: Appointment[]; total: number };
    },
  });

  const appointments = data?.appointments ?? null;
  const total = data?.total ?? 0;

  // Full (up to 500), category-scoped, unfiltered/unpaginated -- unlike
  // `appointments` above (this page's own 10-row slice of the table),
  // stat tiles/tab-count badges/"today's schedule"/lab-queue widgets all
  // need the WHOLE scoped dataset to compute their numbers from. Same
  // "small enough to fetch whole and compute client-side" reasoning this
  // hook always used, just no longer shared with the table's own fetch now
  // that the table itself needs to scale past 500 rows via real pagination.
  const { data: summaryData, refetch: refetchSummary } = useQuery({
    queryKey: ["portal-bookings-summary", category],
    enabled: ready,
    queryFn: async () => {
      const params = new URLSearchParams();
      if (category !== "all") params.set("category", category);
      const result = await portalFetch(`/api/portal/bookings/summary?${params.toString()}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return (result.data as { appointments: Appointment[] }).appointments;
    },
  });
  const allAppointments = summaryData ?? null;

  const error = mutationError ?? (queryError ? "Couldn't load appointments — try again." : null);

  const load = useCallback(() => {
    refetch();
    refetchSummary();
  }, [refetch, refetchSummary]);

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

  const deletableAppointments = (appointments ?? []).filter((a) => a.status !== "booked");

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
      else setMutationError(result.error);
      return;
    }
    const deletedIds = new Set((result.data as { deleted: number[] }).deleted);
    load();
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
    const appointment = appointments?.find((a) => a.id === id);
    setRDoctorId(appointment?.doctor_id || "");
    setRResourceId(appointment?.resource_id != null ? String(appointment.resource_id) : "");
    setRDate("");
    setRSlotId("");
    if (!rescheduleCtx) {
      // Reuses the exact same context endpoint /portal/new-booking already
      // reads doctor/resource slot options from -- no separate endpoint.
      // Department/doctor/resource are fixed to the appointment's own (see
      // rDoctorId/rResourceId above), so only slots_by_doctor[rDoctorId] or
      // slots_by_resource[rResourceId] is actually read out of this.
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
    const appointment = appointments?.find((a) => a.id === id);
    const result = await portalFetch(`/api/portal/bookings/${id}/reschedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        department_id: appointment?.department_id || "", doctor_id: appointment?.doctor_id || rDoctorId,
        resource_id: appointment?.resource_id ?? (rResourceId ? Number(rResourceId) : null),
        slot_id: rSlotId, message: rescheduleMessage.trim(),
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

  // Diagnostic/Lab reschedule follow-up: a resource-bound appointment has no
  // doctor at all -- rResourceId is set instead of rDoctorId when the panel
  // opens (see openReschedulePanel), so exactly one of these two ever has
  // slots to offer.
  const rDatesForDoctor = rescheduleCtx
    ? Object.keys((rDoctorId ? rescheduleCtx.slots_by_doctor[rDoctorId] : rescheduleCtx.slots_by_resource[rResourceId]) || {}).sort()
    : [];
  const rSlotsForDate = rDate && rescheduleCtx
    ? (rDoctorId ? rescheduleCtx.slots_by_doctor[rDoctorId]?.[rDate] : rescheduleCtx.slots_by_resource[rResourceId]?.[rDate]) || []
    : [];

  const selectedAppointments = deletableAppointments.filter((a) => selected.has(a.id));
  const allSelected = deletableAppointments.length > 0 && selected.size === deletableAppointments.length;

  return {
    appointments, allAppointments, error, load, isFetching,
    page, setPage, total, pageSize: PAGE_SIZE,
    searchQuery, setSearchQuery, statusFilter, setStatusFilter, typeFilter, setTypeFilter,
    applyFilters, resetFilters, filtersDirty,
    cancellingId, cancelPanelId, cancelMessage, setCancelMessage, openCancelPanel, closeCancelPanel, handleCancel,
    reschedulePanelId, reschedulingId, rescheduleCtx, rescheduleErrors, rescheduleMessage, setRescheduleMessage,
    rDate, setRDate, rSlotId, setRSlotId,
    rDatesForDoctor, rSlotsForDate,
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
