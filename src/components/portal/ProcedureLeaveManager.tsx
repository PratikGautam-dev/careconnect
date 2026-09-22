"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useProcedureLeave } from "@/hooks/useProcedureLeave";

export function ProcedureLeaveManager({ procedureId }: { procedureId: number }) {
  const { dates, error, newDate, setNewDate, reason, setReason, adding, handleAdd, handleDelete } =
    useProcedureLeave(procedureId);

  return (
    <div className="border-line bg-paper p-space-3 rounded-lg border">
      <p className="text-label mb-space-2 text-ink-900 font-semibold">Downtime / leave dates</p>
      {dates === null ? (
        <p className="text-hint">Loading…</p>
      ) : dates.length === 0 ? (
        <p className="text-hint mb-space-2">No downtime dates set.</p>
      ) : (
        <ul className="mb-space-2 space-y-space-1">
          {dates.map((d) => (
            <li
              key={d}
              className="bg-card px-space-3 py-space-2 flex items-center justify-between rounded-md text-[12.5px]"
            >
              <span className="text-ink-900">{d}</span>
              <button
                type="button"
                onClick={() => handleDelete(d)}
                className="text-ink-400 hover:text-error"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mb-space-2 text-error text-[12.5px]">{error}</p>}
      <div className="gap-space-2 flex flex-wrap items-end">
        <div>
          <label className="mb-space-1 text-ink-400 block text-[11px] font-semibold">Date</label>
          <Input
            type="date"
            value={newDate}
            onChange={(e) => setNewDate(e.target.value)}
            className="w-40"
          />
        </div>
        <Input
          placeholder="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="max-w-[180px]"
        />
        <Button type="button" size="md" onClick={handleAdd} disabled={adding || !newDate}>
          <Plus size={13} /> {adding ? "Adding…" : "Add downtime"}
        </Button>
      </div>
    </div>
  );
}
