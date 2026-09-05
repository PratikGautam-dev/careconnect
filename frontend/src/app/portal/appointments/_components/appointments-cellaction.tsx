"use client";

import { Trash2 } from "lucide-react";
import { PermissionGate } from "@/components/portal/PermissionGate";
import type { Appointment } from "@/hooks/useAppointments";

type AppointmentCellActionProps = {
  appointment: Appointment;
  cancelPanelId: number | null;
  reschedulePanelId: number | null;
  onOpenReschedule: (id: number) => void;
  onOpenCancel: (id: number) => void;
  deletingId: number | null;
  onDelete: (id: number) => void;
};

/** Trailing actions cell -- Reschedule/Cancel for a still-'booked' row
 * (hidden while either inline panel is already open for this row), or
 * Delete for a resolved one (Item 3: only ever offered for a non-'booked'
 * appointment, matching the backend's own guard). */
export function AppointmentCellAction({
  appointment: a,
  cancelPanelId,
  reschedulePanelId,
  onOpenReschedule,
  onOpenCancel,
  deletingId,
  onDelete,
}: AppointmentCellActionProps) {
  if (a.status === "booked") {
    if (cancelPanelId === a.id || reschedulePanelId === a.id) return null;
    return (
      <span className="inline-flex gap-space-3 whitespace-nowrap">
        <button
          type="button"
          onClick={() => onOpenReschedule(a.id)}
          className="text-[12.5px] font-semibold text-brand-600 hover:underline"
        >
          Reschedule
        </button>
        <button
          type="button"
          onClick={() => onOpenCancel(a.id)}
          className="text-[12.5px] font-semibold text-error hover:underline"
        >
          Cancel
        </button>
      </span>
    );
  }

  return (
    <PermissionGate page="appointments" action="delete">
      <button
        type="button"
        onClick={() => onDelete(a.id)}
        disabled={deletingId === a.id}
        className="inline-flex items-center gap-space-1 whitespace-nowrap text-[12.5px] font-semibold text-ink-400 hover:text-error disabled:opacity-50"
      >
        <Trash2 size={12} /> {deletingId === a.id ? "Deleting…" : "Delete"}
      </button>
    </PermissionGate>
  );
}
