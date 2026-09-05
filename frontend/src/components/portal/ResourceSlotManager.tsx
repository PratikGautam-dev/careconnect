"use client";

import { Ban, CheckCircle2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { formatDateHeading } from "@/lib/formatDate";
import { useResourceSlots, type Slot } from "@/hooks/useResourceSlots";

export function ResourceSlotManager({ resourceId }: { resourceId: string }) {
  const {
    date, setDate, viewAll, setViewAll, slots, error, pendingId,
    newDate, setNewDate, newTime, setNewTime, adding,
    groupedByDate, toggleBlock, removeSlot, addSlot,
  } = useResourceSlots(resourceId);

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
          {viewAll ? "No upcoming slots generated for this resource." : "No generated slots on this date."}
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
