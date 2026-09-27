"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

/** "Send reminder" for a single booked appointment -- POST
 * /api/portal/bookings/{id}/send-reminder (portal/routes/bookings.py),
 * same wording as the automatic cron reminder (reminders/scheduler.py's
 * build_reminder_message), just triggered on demand.
 *
 * Deliberately self-contained (owns its own mutation + per-row loading
 * state) rather than threaded down from a page as props -- nothing outside
 * the row that calls sendReminder() needs to react to it, unlike
 * cancelPanelId/reschedulePanelId which also drive page-level UI. This is
 * what lets AppointmentCellAction (shared by both the doctor appointments
 * and diagnostic & lab pages) offer the action without either page's own
 * hook needing to know about it -- any other table that renders an
 * appointment row can call this same hook to get the same action. */
export function useSendAppointmentReminder() {
  const router = useRouter();
  const [sendingReminderId, setSendingReminderId] = useState<number | null>(null);

  const mutation = useMutation({
    mutationFn: async (appointmentId: number) => {
      const result = await portalFetch(`/api/portal/bookings/${appointmentId}/send-reminder`, {
        method: "POST",
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  async function sendReminder(appointmentId: number) {
    setSendingReminderId(appointmentId);
    try {
      await mutation.mutateAsync(appointmentId);
      toast.success("Reminder sent");
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't send reminder", err.message);
    } finally {
      setSendingReminderId(null);
    }
  }

  return { sendingReminderId, sendReminder };
}
