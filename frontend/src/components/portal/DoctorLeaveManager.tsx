"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { portalFetch } from "@/lib/portalAuth";

type LeaveEntry = { id: number; date: string; reason: string | null };

export function DoctorLeaveManager({ doctorId }: { doctorId: string }) {
  const [leave, setLeave] = useState<LeaveEntry[] | null>(null);
  // Item 10 (Spec.md Section 0): From/To range with one Confirm, replacing
  // the old one-date-at-a-time add. A single date is just a range where
  // from === to, so this fully replaces the old single-date form rather
  // than living alongside it.
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [reason, setReason] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/leave`);
    if (result.ok) setLeave((result.data as { leave: LeaveEntry[] }).leave);
  }, [doctorId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd() {
    if (!fromDate || !toDate) return;
    setAdding(true);
    setError(null);
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/leave/range`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from_date: fromDate, to_date: toDate, reason }),
    });
    setAdding(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setFromDate("");
    setToDate("");
    setReason("");
    load();
  }

  async function handleDelete(leaveId: number) {
    await portalFetch(`/api/portal/doctors/${doctorId}/leave/${leaveId}/delete`, { method: "POST" });
    load();
  }

  return (
    <div className="rounded-lg border border-line bg-paper p-space-3">
      <p className="text-label mb-space-2 font-semibold text-ink-900">Leave dates</p>
      {leave === null ? (
        <p className="text-hint">Loading…</p>
      ) : leave.length === 0 ? (
        <p className="text-hint mb-space-2">No leave dates set.</p>
      ) : (
        <ul className="mb-space-2 space-y-space-1">
          {leave.map((l) => (
            <li key={l.id} className="flex items-center justify-between rounded-md bg-card px-space-3 py-space-2 text-[12.5px]">
              <span className="text-ink-900">
                {l.date}
                {l.reason ? ` — ${l.reason}` : ""}
              </span>
              <button type="button" onClick={() => handleDelete(l.id)} className="text-ink-400 hover:text-error">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mb-space-2 text-[12.5px] text-error">{error}</p>}
      <div className="flex flex-wrap items-end gap-space-2">
        <div>
          <label className="mb-space-1 block text-[11px] font-semibold text-ink-400">From</label>
          <Input
            type="date" value={fromDate}
            onChange={(e) => {
              setFromDate(e.target.value);
              // Keep To >= From automatically -- a single day off is just
              // From === To, the common case, so this shouldn't require an
              // extra click for the usual one-day-off entry.
              if (!toDate || toDate < e.target.value) setToDate(e.target.value);
            }}
            className="w-40"
          />
        </div>
        <div>
          <label className="mb-space-1 block text-[11px] font-semibold text-ink-400">To</label>
          <Input type="date" value={toDate} min={fromDate || undefined} onChange={(e) => setToDate(e.target.value)} className="w-40" />
        </div>
        <Input placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} className="max-w-[180px]" />
        <Button type="button" size="md" onClick={handleAdd} disabled={adding || !fromDate || !toDate}>
          <Plus size={13} /> {adding ? "Confirming…" : "Confirm leave"}
        </Button>
      </div>
    </div>
  );
}
