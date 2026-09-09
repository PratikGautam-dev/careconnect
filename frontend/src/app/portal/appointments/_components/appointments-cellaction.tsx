"use client";

import { CalendarClock, Eye, MoreHorizontal, Trash2, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

/** Trailing actions cell -- one combined dropdown menu, same pattern as
 * patients-cellaction.tsx: View Details always offered, plus Reschedule/
 * Cancel for a still-'booked' row (hidden while either inline panel is
 * already open for this row), or Delete for a resolved one (Item 3: only
 * ever offered for a non-'booked' appointment, matching the backend's own
 * guard). */
export function AppointmentCellAction({
  appointment: a,
  cancelPanelId,
  reschedulePanelId,
  onOpenReschedule,
  onOpenCancel,
  deletingId,
  onDelete,
}: AppointmentCellActionProps) {
  const router = useRouter();

  if (a.status === "booked" && (cancelPanelId === a.id || reschedulePanelId === a.id)) return null;

  return (
    <div onClick={(e) => e.stopPropagation()}>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-600 hover:bg-black/4 hover:text-ink-900"
          aria-label={`Actions for appointment ${a.reference_id || a.id}`}
        >
          <MoreHorizontal size={16} />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuGroup>
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => router.push(`/portal/appointments/${a.id}`)}>
              <Eye size={14} /> View Details
            </DropdownMenuItem>
            {a.status === "booked" ? (
              <>
                <DropdownMenuItem onClick={() => onOpenReschedule(a.id)}>
                  <CalendarClock size={14} /> Reschedule
                </DropdownMenuItem>
                <DropdownMenuItem variant="destructive" onClick={() => onOpenCancel(a.id)}>
                  <XCircle size={14} /> Cancel
                </DropdownMenuItem>
              </>
            ) : (
              <PermissionGate page="appointments" action="delete">
                <DropdownMenuItem variant="destructive" disabled={deletingId === a.id} onClick={() => onDelete(a.id)}>
                  <Trash2 size={14} /> {deletingId === a.id ? "Deleting…" : "Delete"}
                </DropdownMenuItem>
              </PermissionGate>
            )}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
