"use client";

import { useCallback, useEffect, useState } from "react";
import { Ban, CheckCircle2 } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

type Slot = { scheduled_at: string; time: string; blocked: boolean; block_reason: string | null; booked: boolean };

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// Item 1 (Spec.md Section 0): a manual per-slot override on top of the
// normal generated availability -- distinct from DoctorLeaveManager (whole
// days) and the doctor's own active/inactive switch (the whole doctor).
export function DoctorSlotManager({ doctorId }: { doctorId: string }) {
  const [date, setDate] = useState(todayIso());
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setSlots(null);
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/slots?date=${date}`);
    if (result.ok) setSlots((result.data as { slots: Slot[] }).slots);
  }, [doctorId, date]);

  useEffect(() => {
    load();
  }, [load]);

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

  return (
    <div className="rounded-lg border border-line bg-paper p-space-3">
      <div className="mb-space-2 flex items-center justify-between">
        <p className="text-label font-semibold text-ink-900">Block individual slots</p>
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" />
      </div>
      {error && <p className="mb-space-2 text-[12.5px] text-error">{error}</p>}
      {slots === null ? (
        <p className="text-hint">Loading…</p>
      ) : slots.length === 0 ? (
        <p className="text-hint">No generated slots on this date.</p>
      ) : (
        <div className="flex flex-wrap gap-space-2">
          {slots.map((s) => (
            <button
              key={s.scheduled_at}
              type="button"
              disabled={pendingId === s.scheduled_at || (s.booked && !s.blocked)}
              onClick={() => toggleBlock(s)}
              title={s.booked && !s.blocked ? "Already booked — cancel or reschedule that appointment first" : s.blocked ? "Tap to unblock" : "Tap to block"}
              className={cn(
                "flex items-center gap-space-1 rounded-md border px-space-2 py-space-1 text-[12px] font-semibold disabled:cursor-not-allowed disabled:opacity-60",
                s.blocked
                  ? "border-error bg-error-tint text-error"
                  : s.booked
                    ? "border-line bg-card text-ink-400"
                    : "border-line bg-card text-ink-700 hover:border-brand-400",
              )}
            >
              {s.blocked ? <Ban size={11} /> : s.booked ? <CheckCircle2 size={11} /> : null}
              {s.time}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
