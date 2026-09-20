import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Slot = {
  scheduled_at: string;
  date: string;
  time: string;
  blocked: boolean;
  block_reason: string | null;
  booked: boolean;
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// A manual per-slot override on top of the normal generated availability,
// distinct from an approved leave request blocking whole days (see
// _apply_approval_side_effects in portal/routes/leave_requests.py) and the
// doctor's own active/inactive switch (the whole doctor). Block/unblock toggles an
// already-generated slot's availability without deleting it; Add/Remove
// actually creates or deletes a doctor_slots row, for a genuinely one-off
// extra slot or permanently dropping one. "View all slots" mode lists
// every upcoming slot across the doctor's whole generated window, grouped
// by date, so removing a specific slot doesn't require knowing its date.
export function useDoctorSlots(doctorId: string) {
  const [date, setDate] = useState(todayIso());
  const [viewAll, setViewAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [newDate, setNewDate] = useState(todayIso());
  const [newTime, setNewTime] = useState("");

  const { data: slots, refetch } = useQuery({
    queryKey: ["portal-doctor-slots", doctorId, viewAll, date],
    retry: false,
    queryFn: async () => {
      const qs = viewAll ? "" : `?date=${date}`;
      const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots${qs}`);
      if (!result.ok) return null;
      return (result.data as { slots: Slot[] }).slots;
    },
  });

  const groupedByDate = useMemo(() => {
    if (!slots) return [];
    const groups = new Map<string, Slot[]>();
    for (const s of slots) {
      if (!groups.has(s.date)) groups.set(s.date, []);
      groups.get(s.date)!.push(s);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [slots]);

  const toggleBlockMutation = useMutation({
    mutationFn: async ({ scheduledAt, blocked }: { scheduledAt: string; blocked: boolean }) => {
      const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots/block`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_at: scheduledAt, blocked }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function toggleBlock(slot: Slot) {
    setPendingId(slot.scheduled_at);
    setError(null);
    try {
      await toggleBlockMutation.mutateAsync({ scheduledAt: slot.scheduled_at, blocked: !slot.blocked });
      toast.success(slot.blocked ? "Slot unblocked" : "Slot blocked");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't update slot", message);
    } finally {
      setPendingId(null);
    }
  }

  const removeSlotMutation = useMutation({
    mutationFn: async (scheduledAt: string) => {
      const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_at: scheduledAt }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function removeSlot(slot: Slot) {
    if (
      !window.confirm(
        `Remove the ${slot.time} slot on ${slot.date}? This deletes it outright, not just blocks it.`,
      )
    )
      return;
    setPendingId(slot.scheduled_at);
    setError(null);
    try {
      await removeSlotMutation.mutateAsync(slot.scheduled_at);
      toast.success("Slot removed");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't remove slot", message);
    } finally {
      setPendingId(null);
    }
  }

  const addSlotMutation = useMutation({
    mutationFn: async ({ addDate, time }: { addDate: string; time: string }) => {
      const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: addDate, time }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function addSlot() {
    if (!newTime) return;
    setError(null);
    try {
      await addSlotMutation.mutateAsync({ addDate: viewAll ? newDate : date, time: newTime });
      toast.success("Slot added");
      setNewTime("");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't add slot", message);
    }
  }

  return {
    date,
    setDate,
    viewAll,
    setViewAll,
    slots: slots ?? null,
    error,
    pendingId,
    newDate,
    setNewDate,
    newTime,
    setNewTime,
    adding: addSlotMutation.isPending,
    groupedByDate,
    toggleBlock,
    removeSlot,
    addSlot,
  };
}
