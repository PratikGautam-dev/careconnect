"use client";

import { Ban, CheckCircle2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { formatDateHeading } from "@/lib/formatDate";
import { useProcedureSlots, type Slot } from "@/hooks/useProcedureSlots";

export function ProcedureSlotManager({ procedureId }: { procedureId: number }) {
  const {
    date,
    setDate,
    viewAll,
    setViewAll,
    slots,
    error,
    pendingId,
    newDate,
    setNewDate,
    newTime,
    setNewTime,
    adding,
    groupedByDate,
    toggleBlock,
    removeSlot,
    addSlot,
  } = useProcedureSlots(procedureId);

  function renderSlotPill(s: Slot) {
    return (
      <span
        key={s.scheduled_at}
        className={cn(
          "group gap-space-1 px-space-2 py-space-1 flex items-center rounded-md border text-[12px] font-semibold",
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
          title={
            s.booked && !s.blocked
              ? "Already booked — cancel or reschedule that appointment first"
              : s.blocked
                ? "Tap to unblock"
                : "Tap to block"
          }
          className="gap-space-1 flex items-center disabled:cursor-not-allowed disabled:opacity-60"
        >
          {s.blocked ? <Ban size={11} /> : s.booked ? <CheckCircle2 size={11} /> : null}
          {s.time}
        </button>
        <button
          type="button"
          disabled={pendingId === s.scheduled_at || s.booked}
          onClick={() => removeSlot(s)}
          title={
            s.booked
              ? "Already booked — cancel or reschedule that appointment first"
              : "Remove this slot entirely"
          }
          className="text-ink-300 hover:text-error disabled:cursor-not-allowed disabled:opacity-40"
        >
          <X size={11} />
        </button>
      </span>
    );
  }

  return (
    <div className="border-line bg-paper p-space-3 rounded-lg border">
      <div className="mb-space-2 gap-space-2 flex flex-wrap items-center justify-between">
        <p className="text-label text-ink-900 font-semibold">Manage individual slots</p>
        <div className="gap-space-2 flex items-center">
          {!viewAll && (
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-40"
            />
          )}
          <button
            type="button"
            onClick={() => setViewAll((v) => !v)}
            className="text-brand-600 text-[12px] font-semibold hover:underline"
          >
            {viewAll ? "Show one date" : "View all upcoming slots"}
          </button>
        </div>
      </div>
      {error && <p className="mb-space-2 text-error text-[12.5px]">{error}</p>}
      {slots === null ? (
        <p className="text-hint">Loading…</p>
      ) : slots.length === 0 ? (
        <p className="mb-space-2 text-hint">
          {viewAll
            ? "No upcoming slots generated for this procedure."
            : "No generated slots on this date."}
        </p>
      ) : viewAll ? (
        <div className="mb-space-3 space-y-space-2 max-h-64 overflow-y-auto">
          {groupedByDate.map(([d, daySlots]) => (
            <div key={d}>
              <p className="mb-space-1 text-ink-400 text-[11px] font-semibold">
                {formatDateHeading(d)}
              </p>
              <div className="gap-space-2 flex flex-wrap">{daySlots.map(renderSlotPill)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mb-space-3 gap-space-2 flex flex-wrap">{slots.map(renderSlotPill)}</div>
      )}
      <div className="gap-space-2 border-line pt-space-2 flex flex-wrap items-center border-t">
        {viewAll && (
          <Input
            type="date"
            value={newDate}
            onChange={(e) => setNewDate(e.target.value)}
            className="w-40"
          />
        )}
        <Input
          type="time"
          value={newTime}
          onChange={(e) => setNewTime(e.target.value)}
          className="w-32"
        />
        <Button type="button" size="md" onClick={addSlot} disabled={adding || !newTime}>
          <Plus size={13} /> {adding ? "Adding…" : "Add a slot"}
        </Button>
      </div>
    </div>
  );
}
