"use client";

import { useMemo } from "react";
import { CalendarClock, Plus, Search, Send, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { TYPE_LABELS, type Appointment, useAppointments } from "@/hooks/useAppointments";
import { createAppointmentColumns, STATUS_LABELS } from "./_components/appointments-columns";

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
    advancingLabStatusId, handleAdvanceLabStatus,
    deletingId, handleDelete,
    selected, toggleSelected, toggleSelectAll, deletableAppointments, selectedAppointments, allSelected,
    pendingDelete, setPendingDelete, bulkDeleting, runBulkDelete,
  } = useAppointments(ready);

  const columns = useMemo(
    () =>
      createAppointmentColumns({
        selected, toggleSelected, toggleSelectAll, allSelected,
        deletableCount: deletableAppointments.length,
        markingAttendanceId, onAttendance: handleAttendance,
        advancingLabStatusId, onAdvanceLabStatus: handleAdvanceLabStatus,
        cancelPanelId, reschedulePanelId,
        onOpenReschedule: openReschedulePanel, onOpenCancel: openCancelPanel,
        deletingId, onDelete: handleDelete,
      }),
    [
      selected, toggleSelected, toggleSelectAll, allSelected, deletableAppointments.length,
      markingAttendanceId, handleAttendance, advancingLabStatusId, handleAdvanceLabStatus,
      cancelPanelId, reschedulePanelId, openReschedulePanel, openCancelPanel, deletingId, handleDelete,
    ],
  );

  function renderRowDetail(a: Appointment) {
    if (reschedulePanelId === a.id) {
      return (
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
      );
    }

    if (cancelPanelId === a.id) {
      return (
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
      );
    }

    return null;
  }

  return (
    <PortalShell hospital={hospital} active="appointments">
        <PageHeader
          title="Appointments"
          actions={
            <>
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
            </>
          }
        />

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
            <DataTable
              columns={columns}
              data={filteredAppointments || []}
              getRowId={(a) => String(a.id)}
              isRowExpanded={(a) => reschedulePanelId === a.id || cancelPanelId === a.id}
              renderRowDetail={renderRowDetail}
            />
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
