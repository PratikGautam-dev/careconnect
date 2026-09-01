"use client";

import { Fragment } from "react";
import { CalendarClock, Plus, Search, Send, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import { TYPE_LABELS, useAppointments } from "@/hooks/useAppointments";

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
const TYPE_TAB_ORDER = ["all", "new", "followup", "tele", "second_opinion", "diagnostic", "lab", "daycare", "other"];

export default function PortalAppointmentsPage() {
  const { hospital, ready } = usePortalGuard();
  const {
    appointments, error, filteredAppointments, typeCounts,
    searchQuery, setSearchQuery, statusFilter, setStatusFilter, typeFilter, setTypeFilter,
    cancellingId, cancelPanelId, cancelMessage, setCancelMessage, openCancelPanel, closeCancelPanel, handleCancel,
    reschedulePanelId, reschedulingId, rescheduleCtx, rescheduleErrors, rescheduleMessage, setRescheduleMessage,
    rDepartmentId, setRDepartmentId, rDoctorId, setRDoctorId, rDate, setRDate, rSlotId, setRSlotId,
    rDoctors, rDatesForDoctor, rSlotsForDate,
    openReschedulePanel, closeReschedulePanel, handleReschedule,
    markingAttendanceId, handleAttendance,
    deletingId, handleDelete,
    selected, toggleSelected, toggleSelectAll, deletableAppointments, selectedAppointments, allSelected,
    pendingDelete, setPendingDelete, bulkDeleting, runBulkDelete,
  } = useAppointments(ready);

  return (
    <PortalShell hospital={hospital} active="appointments">
        <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
          <h1 className="text-display">Appointments</h1>
          <div className="flex items-center gap-space-2">
            {selectedAppointments.length > 0 && (
              <PermissionGate page="appointments" action="delete">
                <Button
                  variant="secondary"
                  size="md"
                  className="border-error/30 text-error hover:border-error hover:bg-error/10"
                  onClick={() => setPendingDelete(selectedAppointments)}
                >
                  <Trash2 size={15} />
                  Delete selected ({selectedAppointments.length})
                </Button>
              </PermissionGate>
            )}
            <Button href="/portal/new-booking">
              <Plus size={15} /> New booking
            </Button>
          </div>
        </div>

        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        {/* Divides the list by appointment type -- a tab per type (plus
            "Other" for the rare pre-appointment-type-feature row), each
            showing how many currently match, "All" always first. */}
        <div className="mb-space-4 flex flex-wrap gap-space-2">
          {TYPE_TAB_ORDER.filter((id) => id === "all" || (typeCounts[id] || 0) > 0 || typeFilter === id).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTypeFilter(id)}
              className={cn(
                "rounded-full border px-space-3 py-space-1 text-[12.5px] font-semibold transition-colors duration-150",
                typeFilter === id
                  ? "border-brand-600 bg-brand-600 text-white"
                  : "border-line bg-card text-ink-600 hover:border-brand-300 hover:bg-brand-50",
              )}
            >
              {id === "all" ? "All" : id === "other" ? "Other" : TYPE_LABELS[id]}
              <span className={cn("ml-space-1 tabular-nums", typeFilter === id ? "text-white/80" : "text-ink-400")}>
                {typeCounts[id] || 0}
              </span>
            </button>
          ))}
        </div>

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
                    <th className="w-8 pb-space-2 font-semibold">
                      <PermissionGate page="appointments" action="delete">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={(e) => toggleSelectAll(e.target.checked)}
                          disabled={deletableAppointments.length === 0}
                          className="h-4 w-4 accent-brand-600"
                          aria-label="Select all deletable appointments"
                        />
                      </PermissionGate>
                    </th>
                    <th className="pb-space-2 font-semibold">Appointment time</th>
                    <th className="pb-space-2 font-semibold">Booked</th>
                    <th className="pb-space-2 font-semibold">Reference</th>
                    <th className="pb-space-2 font-semibold">Patient</th>
                    <th className="pb-space-2 font-semibold">Doctor</th>
                    <th className="pb-space-2 font-semibold">Department</th>
                    <th className="pb-space-2 font-semibold">Type</th>
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
                        <td className="py-space-2" onClick={(e) => e.stopPropagation()}>
                          {a.status !== "booked" && (
                            <PermissionGate page="appointments" action="delete">
                              <input
                                type="checkbox"
                                checked={selected.has(a.id)}
                                onChange={(e) => toggleSelected(a.id, e.target.checked)}
                                className="h-4 w-4 accent-brand-600"
                                aria-label={`Select appointment ${a.reference_id || a.id}`}
                              />
                            </PermissionGate>
                          )}
                        </td>
                        <td className="py-space-2 whitespace-nowrap tabular-nums text-ink-600">{formatShortDateTime(a.scheduled_at)}</td>
                        <td className="py-space-2 whitespace-nowrap tabular-nums text-ink-400">
                          {a.created_at ? formatShortDateTime(a.created_at) : "—"}
                        </td>
                        <td className="py-space-2 whitespace-nowrap font-mono text-[12px] text-ink-400">{a.reference_id || "—"}</td>
                        <td className="py-space-2 text-ink-900">
                          <div>{a.phone}</div>
                          {a.patient_display_id && (
                            <div className="font-mono text-[11px] text-ink-400">{a.patient_display_id}</div>
                          )}
                        </td>
                        <td className="py-space-2 text-ink-600">{a.doctor_name}</td>
                        <td className="py-space-2 text-ink-600">{a.department_name}</td>
                        <td className="py-space-2 text-ink-600">
                          <div>{a.appointment_type_id ? TYPE_LABELS[a.appointment_type_id] || a.appointment_type_id : "—"}</div>
                          {/* Tele-consultation Phase 2 (confirmed with the
                              user directly): staff need the video link too,
                              not just the doctor's own "Today's appointments"
                              widget -- withheld from the patient's immediate
                              confirmation, but always visible here. */}
                          {a.appointment_type_id === "tele" && a.video_link && (
                            <a
                              href={a.video_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11.5px] font-semibold text-brand-600 hover:underline"
                            >
                              🎥 Join
                            </a>
                          )}
                        </td>
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
                            <PermissionGate page="appointments" action="delete">
                              <button
                                type="button"
                                onClick={() => handleDelete(a.id)}
                                disabled={deletingId === a.id}
                                className="inline-flex items-center gap-space-1 text-[12.5px] font-semibold text-ink-400 hover:text-error disabled:opacity-50"
                              >
                                <Trash2 size={12} /> {deletingId === a.id ? "Deleting…" : "Delete"}
                              </button>
                            </PermissionGate>
                          )}
                        </td>
                      </tr>
                      {reschedulePanelId === a.id && (
                        <tr className="border-b border-line last:border-0">
                          <td colSpan={12} className="pb-space-3">
                            <div className="rounded-lg border border-line bg-paper p-space-3">
                              <div className="mb-space-3 grid grid-cols-1 gap-x-space-3 gap-y-space-2 md:grid-cols-2">
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
                          <td colSpan={12} className="pb-space-3">
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

        <ConfirmDialog
          open={pendingDelete !== null}
          title={pendingDelete && pendingDelete.length > 1 ? `Delete ${pendingDelete.length} appointments?` : "Delete appointment?"}
          message={
            pendingDelete
              ? `This will permanently delete ${
                  pendingDelete.length > 1 ? `${pendingDelete.length} appointment records` : `the ${pendingDelete[0].reference_id || "selected"} appointment`
                }. This action is irreversible.`
              : ""
          }
          confirmLabel="Delete"
          destructive
          busy={bulkDeleting}
          onConfirm={() => pendingDelete && runBulkDelete(pendingDelete)}
          onCancel={() => setPendingDelete(null)}
        />
    </PortalShell>
  );
}
