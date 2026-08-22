"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Ban, CheckCircle2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

type Slot = { scheduled_at: string; date: string; time: string; blocked: boolean; block_reason: string | null; booked: boolean };

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function formatDateHeading(dateStr: string) {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

// Item 1 (Spec.md Section 0) + add/remove follow-up: a manual per-slot
// override on top of the normal generated availability -- distinct from
// DoctorLeaveManager (whole days) and the doctor's own active/inactive
// switch (the whole doctor). Block/unblock toggles an already-generated
// slot's availability without deleting it; Add/Remove actually creates or
// deletes a doctor_slots row -- for a genuinely one-off extra slot (e.g. a
// special clinic day) or permanently dropping one, not just hiding it.
// "View all slots" mode (vs. the original one-date-at-a-time view) lists
// every upcoming slot across the doctor's whole generated window, grouped
// by date, so removing a specific slot doesn't require already knowing
// which date it falls on.
export function DoctorSlotManager({ doctorId }: { doctorId: string }) {
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
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots${qs}`);
    if (result.ok) setSlots((result.data as { slots: Slot[] }).slots);
  }, [doctorId, date, viewAll]);

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
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots/block`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_at: slot.scheduled_at, blocked: !slot.blocked }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    load();
  }

  async function removeSlot(slot: Slot) {
    if (!window.confirm(`Remove the ${slot.time} slot on ${slot.date}? This deletes it outright, not just blocks it.`)) return;
    setPendingId(slot.scheduled_at);
    setError(null);
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_at: slot.scheduled_at }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    load();
  }

  async function addSlot() {
    if (!newTime) return;
    setAdding(true);
    setError(null);
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: viewAll ? newDate : date, time: newTime }),
    });
    setAdding(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNewTime("");
    load();
  }

  function renderSlotPill(s: Slot) {
    return (
      <span
        key={s.scheduled_at}
        className={cn(
          "group flex items-center gap-space-1 rounded-md border px-space-2 py-space-1 text-[12px] font-semibold",
          s.blocked
            ? "border-error bg-error-tint text-error"
            : s.booked
              ? "border-line bg-card text-ink-400"
              : "border-line bg-card text-ink-700",
        )}
      >
        <button
          type="button"
          disabled={pendingId === s.scheduled_at || (s.booked && !s.blocked)}
          onClick={() => toggleBlock(s)}
          title={s.booked && !s.blocked ? "Already booked — cancel or reschedule that appointment first" : s.blocked ? "Tap to unblock" : "Tap to block"}
          className="flex items-center gap-space-1 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {s.blocked ? <Ban size={11} /> : s.booked ? <CheckCircle2 size={11} /> : null}
          {s.time}
        </button>
        <button
          type="button"
          disabled={pendingId === s.scheduled_at || s.booked}
          onClick={() => removeSlot(s)}
          title={s.booked ? "Already booked — cancel or reschedule that appointment first" : "Remove this slot entirely"}
          className="text-ink-300 hover:text-error disabled:cursor-not-allowed disabled:opacity-40"
        >
          <X size={11} />
        </button>
      </span>
    );
  }

  return (
    <div className="rounded-lg border border-line bg-paper p-space-3">
      <div className="mb-space-2 flex flex-wrap items-center justify-between gap-space-2">
        <p className="text-label font-semibold text-ink-900">Manage individual slots</p>
        <div className="flex items-center gap-space-2">
          {!viewAll && <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" />}
          <button
            type="button"
            onClick={() => setViewAll((v) => !v)}
            className="text-[12px] font-semibold text-brand-600 hover:underline"
          >
            {viewAll ? "Show one date" : "View all upcoming slots"}
          </button>
        </div>
      </div>
      {error && <p className="mb-space-2 text-[12.5px] text-error">{error}</p>}
      {slots === null ? (
        <p className="text-hint">Loading…</p>
      ) : slots.length === 0 ? (
        <p className="mb-space-2 text-hint">
          {viewAll ? "No upcoming slots generated for this doctor." : "No generated slots on this date."}
        </p>
      ) : viewAll ? (
        <div className="mb-space-3 max-h-64 space-y-space-2 overflow-y-auto">
          {groupedByDate.map(([d, daySlots]) => (
            <div key={d}>
              <p className="mb-space-1 text-[11px] font-semibold text-ink-400">{formatDateHeading(d)}</p>
              <div className="flex flex-wrap gap-space-2">{daySlots.map(renderSlotPill)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mb-space-3 flex flex-wrap gap-space-2">{slots.map(renderSlotPill)}</div>
      )}
      <div className="flex flex-wrap items-center gap-space-2 border-t border-line pt-space-2">
        {viewAll && <Input type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} className="w-40" />}
        <Input type="time" value={newTime} onChange={(e) => setNewTime(e.target.value)} className="w-32" />
        <Button type="button" size="md" onClick={addSlot} disabled={adding || !newTime}>
          <Plus size={13} /> {adding ? "Adding…" : "Add a slot"}
        </Button>
      </div>
    </div>
  );
}
