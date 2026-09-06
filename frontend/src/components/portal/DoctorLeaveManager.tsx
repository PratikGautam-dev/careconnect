"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useDoctorLeave } from "@/hooks/useDoctorLeave";

export function DoctorLeaveManager({ doctorId }: { doctorId: string }) {
  const {
    leave, error,
    fromDate, setFromDate, toDate, setToDate, reason, setReason, adding,
    handleAdd, handleDelete,
  } = useDoctorLeave(doctorId);

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
