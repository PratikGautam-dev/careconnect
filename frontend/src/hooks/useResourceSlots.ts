import { useCallback, useEffect, useMemo, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Slot = { scheduled_at: string; date: string; time: string; blocked: boolean; block_reason: string | null; booked: boolean };

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// Diagnostic/Lab Phase 2: the resource-scoped sibling of useDoctorSlots --
// same manual per-slot override shape, pointed at /api/portal/diagnostic-
// resources/{resourceId}/slots... instead of /api/portal/doctors/....
export function useResourceSlots(resourceId: string) {
  const [date, setDate] = useState(todayIso());
  const [viewAll, setViewAll] = useState(false);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [newDate, setNewDate] = useState(todayIso());
  const [newTime, setNewTime] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setSlots(null);
    const qs = viewAll ? "" : `?date=${date}`;
    const result = await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/slots${qs}`);
    if (result.ok) setSlots((result.data as { slots: Slot[] }).slots);
  }, [resourceId, date, viewAll]);

  useEffect(() => {
    load();
  }, [load]);

  const groupedByDate = useMemo(() => {
    if (!slots) return [];
    const groups = new Map<string, Slot[]>();
    for (const s of slots) {
      if (!groups.has(s.date)) groups.set(s.date, []);
      groups.get(s.date)!.push(s);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [slots]);

  async function toggleBlock(slot: Slot) {
    setPendingId(slot.scheduled_at);
    setError(null);
    const result = await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/slots/block`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_at: slot.scheduled_at, blocked: !slot.blocked }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't update slot", result.error);
      return;
    }
    toast.success(slot.blocked ? "Slot unblocked" : "Slot blocked");
    load();
  }

  async function removeSlot(slot: Slot) {
    if (!window.confirm(`Remove the ${slot.time} slot on ${slot.date}? This deletes it outright, not just blocks it.`)) return;
    setPendingId(slot.scheduled_at);
    setError(null);
    const result = await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/slots/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_at: slot.scheduled_at }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't remove slot", result.error);
      return;
    }
    toast.success("Slot removed");
    load();
  }

  async function addSlot() {
    if (!newTime) return;
    setAdding(true);
    setError(null);
    const result = await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/slots/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: viewAll ? newDate : date, time: newTime }),
    });
    setAdding(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't add slot", result.error);
      return;
    }
    toast.success("Slot added");
    setNewTime("");
    load();
  }

  return {
    date, setDate, viewAll, setViewAll, slots, error, pendingId,
    newDate, setNewDate, newTime, setNewTime, adding,
    groupedByDate, toggleBlock, removeSlot, addSlot,
  };
}
