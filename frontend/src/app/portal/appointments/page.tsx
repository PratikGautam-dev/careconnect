"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, Plus, Search, Send, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

const DEFAULT_CANCEL_MESSAGE = "Your appointment has been cancelled.";
const DEFAULT_RESCHEDULE_MESSAGE = "Your appointment has been rescheduled.";

type Appointment = {
  id: number;
  phone: string;
  department_name: string;
  doctor_name: string;
  scheduled_at: string;
  status: string;
  source: string;
  reference_id: string | null;
};

type Department = { id: string; name: string };
type Doctor = { id: string; name: string };
type Slot = { id: string; label: string };
type NewBookingContext = {
  departments: Department[];
  doctors_by_department: Record<string, Doctor[]>;
  slots_by_doctor: Record<string, Record<string, Slot[]>>;
};

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};
const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled",
  attended: "Attended", no_show: "No-show",
};
const SOURCE_LABELS: Record<string, string> = { whatsapp: "WhatsApp", staff: "Walk-in" };

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function PortalAppointmentsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
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

  // Item 2 (Spec.md Section 0): search (patient phone / doctor / department
  // name) + status filter -- computed client-side, same reasoning the
  // doctors page below uses (this list is already bounded to 500 rows by
  // the backend, small enough that a server round-trip per keystroke isn't
  // needed).
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Item 9 (Spec.md Section 0): closes the "no-shows are a heuristic, not a
  // real status" gap -- a still-'booked' appointment whose scheduled time
  // has already passed gets an inline "Did the patient visit?" prompt,
  // computed here from the same fields the table already has (no separate
  // fetch needed just to know which rows these are).
  async function handleAttendance(id: number, attended: boolean) {
    setMarkingAttendanceId(id);
    const result = await portalFetch(`/api/portal/bookings/${id}/attendance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attended }),
    });
    setMarkingAttendanceId(null);
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

  const filteredAppointments = useMemo(() => {
    if (!appointments) return appointments;
    const q = searchQuery.trim().toLowerCase();
    return appointments.filter((a) => {
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (!q) return true;
      return (
        a.phone.toLowerCase().includes(q) ||
        a.doctor_name.toLowerCase().includes(q) ||
        a.department_name.toLowerCase().includes(q) ||
        (a.reference_id || "").toLowerCase().includes(q)
      );
    });
  }, [appointments, searchQuery, statusFilter]);

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

  return (
    <PortalShell hospital={hospital} active="appointments">
        <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
          <h1 className="text-display">Appointments</h1>
          <Button href="/portal/new-booking">
            <Plus size={15} /> New booking
          </Button>
        </div>

        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <div className="mb-space-4 flex flex-wrap items-center gap-space-3">
          <div className="relative min-w-[220px] flex-1">
            <Search size={14} className="pointer-events-none absolute left-space-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <input
              type="text"
              placeholder="Search phone, doctor, department, or reference…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-full rounded-md border border-line bg-card pl-space-8 pr-space-3 text-[13px] text-ink-900 outline-none focus:border-brand-400"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
          >
            <option value="all">All statuses</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <Card className="p-space-4">
          {!appointments ? (
            <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
          ) : appointments.length === 0 ? (
            <p className="py-space-4 text-center text-[13px] text-ink-400">No appointments yet.</p>
          ) : filteredAppointments && filteredAppointments.length === 0 ? (
            <p className="py-space-4 text-center text-[13px] text-ink-400">No appointments match your search/filter.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="border-b border-line text-[11.5px] text-ink-400 uppercase">
                    <th className="pb-space-2 font-semibold">Time</th>
                    <th className="pb-space-2 font-semibold">Reference</th>
                    <th className="pb-space-2 font-semibold">Patient</th>
                    <th className="pb-space-2 font-semibold">Doctor</th>
                    <th className="pb-space-2 font-semibold">Department</th>
                    <th className="pb-space-2 font-semibold">Source</th>
                    <th className="pb-space-2 font-semibold">Status</th>
                    <th className="pb-space-2 font-semibold">Visited</th>
                    <th className="pb-space-2 font-semibold"></th>
                  </tr>
                </thead>
                <tbody>
                  {(filteredAppointments || []).map((a) => (
                    <Fragment key={a.id}>
                      <tr className={cn("border-b border-line last:border-0", (cancelPanelId === a.id || reschedulePanelId === a.id) && "border-b-0")}>
                        <td className="py-space-2 whitespace-nowrap tabular-nums text-ink-600">{formatTime(a.scheduled_at)}</td>
                        <td className="py-space-2 whitespace-nowrap font-mono text-[12px] text-ink-400">{a.reference_id || "—"}</td>
                        <td className="py-space-2 text-ink-900">{a.phone}</td>
                        <td className="py-space-2 text-ink-600">{a.doctor_name}</td>
                        <td className="py-space-2 text-ink-600">{a.department_name}</td>
                        <td className="py-space-2 text-ink-600">{SOURCE_LABELS[a.source] || a.source}</td>
                        <td className="py-space-2">
                          <span
                            className={cn(
                              "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                              STATUS_STYLES[a.status] || "bg-black/[0.04] text-ink-600",
                            )}
                          >
                            {STATUS_LABELS[a.status] || a.status}
                          </span>
                        </td>
                        <td className="py-space-2 whitespace-nowrap">
                          {a.status === "booked" || a.status === "attended" || a.status === "no_show" ? (
                            // Admin-editable at any time, not gated on the
                            // scheduled time having passed, and freely
                            // re-toggleable (not a one-way door) -- per
                            // direct portal feedback.
                            <span className="inline-flex items-center gap-space-2">
                              <button
                                type="button"
                                onClick={() => handleAttendance(a.id, true)}
                                disabled={markingAttendanceId === a.id}
                                className={cn(
                                  "text-[12.5px] font-semibold disabled:opacity-50",
                                  a.status === "attended" ? "text-success underline" : "text-ink-400 hover:text-success hover:underline",
                                )}
                              >
                                Yes
                              </button>
                              <span className="text-ink-300">/</span>
                              <button
                                type="button"
                                onClick={() => handleAttendance(a.id, false)}
                                disabled={markingAttendanceId === a.id}
                                className={cn(
                                  "text-[12.5px] font-semibold disabled:opacity-50",
                                  a.status === "no_show" ? "text-error underline" : "text-ink-400 hover:text-error hover:underline",
                                )}
                              >
                                No
                              </button>
                            </span>
                          ) : (
                            <span className="text-[12.5px] text-ink-300">—</span>
                          )}
                        </td>
                        <td className="py-space-2 text-right whitespace-nowrap">
                          {a.status === "booked" ? (
                            cancelPanelId !== a.id && reschedulePanelId !== a.id && (
                              <span className="inline-flex gap-space-3">
                                <button
                                  type="button"
                                  onClick={() => openReschedulePanel(a.id)}
                                  className="text-[12.5px] font-semibold text-brand-600 hover:underline"
                                >
                                  Reschedule
                                </button>
                                <button
                                  type="button"
                                  onClick={() => openCancelPanel(a.id)}
                                  className="text-[12.5px] font-semibold text-error hover:underline"
                                >
                                  Cancel
                                </button>
                              </span>
                            )
                          ) : (
                            // Item 3: delete only ever offered for a resolved
                            // (non-'booked') appointment -- matches the
                            // backend's own guard.
                            <button
                              type="button"
                              onClick={() => handleDelete(a.id)}
                              disabled={deletingId === a.id}
                              className="inline-flex items-center gap-space-1 text-[12.5px] font-semibold text-ink-400 hover:text-error disabled:opacity-50"
                            >
                              <Trash2 size={12} /> {deletingId === a.id ? "Deleting…" : "Delete"}
                            </button>
                          )}
                        </td>
                      </tr>
                      {reschedulePanelId === a.id && (
                        <tr className="border-b border-line last:border-0">
                          <td colSpan={9} className="pb-space-3">
                            <div className="rounded-lg border border-line bg-paper p-space-3">
                              <div className="mb-space-3 grid grid-cols-1 gap-x-space-3 gap-y-space-2 sm:grid-cols-2">
                                <div>
                                  <label className="mb-space-1 block text-[12px] font-semibold text-ink-600">Department</label>
                                  <select
                                    value={rDepartmentId}
                                    onChange={(e) => { setRDepartmentId(e.target.value); setRDoctorId(""); setRDate(""); setRSlotId(""); }}
                                    className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900"
                                  >
                                    <option value="">Choose…</option>
                                    {(rescheduleCtx?.departments || []).map((d) => (
                                      <option key={d.id} value={d.id}>{d.name}</option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label className="mb-space-1 block text-[12px] font-semibold text-ink-600">Doctor</label>
                                  <select
                                    value={rDoctorId}
                                    onChange={(e) => { setRDoctorId(e.target.value); setRDate(""); setRSlotId(""); }}
                                    disabled={!rDepartmentId}
                                    className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-900 disabled:cursor-not-allowed disabled:bg-paper"
                                  >
                                    <option value="">Choose…</option>
                                    {rDoctors.map((d) => (
                                      <option key={d.id} value={d.id}>{d.name}</option>
                                    ))}
                                  </select>
                                </div>
                              </div>

                              {rDoctorId && (
                                <div className="mb-space-2">
                                  <label className="mb-space-1 block text-[12px] font-semibold text-ink-600">Date</label>
                                  {rDatesForDoctor.length === 0 ? (
                                    <p className="text-[12.5px] text-ink-400">No available dates for this doctor.</p>
                                  ) : (
                                    <div className="flex flex-wrap gap-space-2">
                                      {rDatesForDoctor.map((d) => (
                                        <button
                                          type="button" key={d}
                                          onClick={() => { setRDate(d); setRSlotId(""); }}
                                          className={cn(
                                            "rounded-md border px-space-2 py-space-1 text-[12px] font-semibold",
                                            rDate === d ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600",
                                          )}
                                        >
                                          {d}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}

                              {rDate && (
                                <div className="mb-space-3">
                                  <label className="mb-space-1 block text-[12px] font-semibold text-ink-600">Time slot</label>
                                  {rSlotsForDate.length === 0 ? (
                                    <p className="text-[12.5px] text-ink-400">No slots available on this date.</p>
                                  ) : (
                                    <div className="flex flex-wrap gap-space-2">
                                      {rSlotsForDate.map((s) => (
                                        <button
                                          type="button" key={s.id}
                                          onClick={() => setRSlotId(s.id)}
                                          className={cn(
                                            "rounded-md border px-space-2 py-space-1 text-[12px] font-semibold",
                                            rSlotId === s.id ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600",
                                          )}
                                        >
                                          {s.label}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}

                              <label htmlFor={`reschedule-msg-${a.id}`} className="mb-space-2 block text-[12px] font-semibold text-ink-600">
                                Message to send {a.phone} on WhatsApp (optional)
                              </label>
                              <textarea
                                id={`reschedule-msg-${a.id}`}
                                value={rescheduleMessage}
                                onChange={(e) => setRescheduleMessage(e.target.value)}
                                rows={2}
                                className="mb-space-2 h-16 w-full resize-none rounded-md border border-line bg-card px-space-3 py-space-2 text-[13px] text-ink-900 outline-none focus:border-brand-400"
                              />

                              {rescheduleErrors.length > 0 && (
                                <div className="mb-space-2 rounded-md border border-error bg-error-tint p-space-2 text-[12px] text-error">
                                  <ul className="list-disc pl-space-4">
                                    {rescheduleErrors.map((e, i) => <li key={i}>{e}</li>)}
                                  </ul>
                                </div>
                              )}

                              <div className="flex gap-space-2">
                                <Button
                                  size="md"
                                  onClick={() => handleReschedule(a.id)}
                                  disabled={reschedulingId === a.id || !rSlotId}
                                >
                                  <CalendarClock size={13} /> {reschedulingId === a.id ? "Rescheduling…" : "Send & reschedule"}
                                </Button>
                                <Button size="md" variant="secondary" onClick={closeReschedulePanel} disabled={reschedulingId === a.id}>
                                  <X size={13} /> Dismiss
                                </Button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                      {cancelPanelId === a.id && (
                        <tr className="border-b border-line last:border-0">
                          <td colSpan={9} className="pb-space-3">
                            <div className="rounded-lg border border-line bg-paper p-space-3">
                              <label htmlFor={`cancel-msg-${a.id}`} className="mb-space-2 block text-[12px] font-semibold text-ink-600">
                                Message to send {a.phone} on WhatsApp
                              </label>
                              <textarea
                                id={`cancel-msg-${a.id}`}
                                value={cancelMessage}
                                onChange={(e) => setCancelMessage(e.target.value)}
                                rows={2}
                                className="mb-space-2 h-16 w-full resize-none rounded-md border border-line bg-card px-space-3 py-space-2 text-[13px] text-ink-900 outline-none focus:border-brand-400"
                              />
                              <div className="flex gap-space-2">
                                <Button
                                  size="md"
                                  onClick={() => handleCancel(a.id)}
                                  disabled={cancellingId === a.id}
                                  className="bg-error hover:bg-error/90 active:bg-error/80"
                                >
                                  <Send size={13} /> {cancellingId === a.id ? "Cancelling…" : "Send & cancel"}
                                </Button>
                                <Button size="md" variant="secondary" onClick={closeCancelPanel} disabled={cancellingId === a.id}>
                                  <X size={13} /> Dismiss
                                </Button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
    </PortalShell>
  );
}
