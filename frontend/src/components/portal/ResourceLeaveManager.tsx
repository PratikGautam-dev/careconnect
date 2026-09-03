"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { portalFetch } from "@/lib/portalAuth";

// Diagnostic/Lab Phase 2: whole-day resource unavailability (maintenance,
// downtime) -- simpler than DoctorLeaveManager's id-based CRUD since the
// backend here keys leave by date directly, one date at a time.
export function ResourceLeaveManager({ resourceId }: { resourceId: string }) {
  const [dates, setDates] = useState<string[] | null>(null);
  const [newDate, setNewDate] = useState("");
  const [reason, setReason] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/leave`);
    if (result.ok) setDates((result.data as { leave_dates: string[] }).leave_dates);
  }, [resourceId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd() {
    if (!newDate) return;
    setAdding(true);
    setError(null);
    const result = await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/leave`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: newDate, reason }),
    });
    setAdding(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    setNewDate("");
    setReason("");
    load();
  }

  async function handleDelete(date: string) {
    await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/leave/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
    load();
  }

  return (
    <div className="rounded-lg border border-line bg-paper p-space-3">
      <p className="text-label mb-space-2 font-semibold text-ink-900">Downtime / leave dates</p>
      {dates === null ? (
        <p className="text-hint">Loading…</p>
      ) : dates.length === 0 ? (
        <p className="text-hint mb-space-2">No downtime dates set.</p>
      ) : (
        <ul className="mb-space-2 space-y-space-1">
          {dates.map((d) => (
            <li key={d} className="flex items-center justify-between rounded-md bg-card px-space-3 py-space-2 text-[12.5px]">
              <span className="text-ink-900">{d}</span>
              <button type="button" onClick={() => handleDelete(d)} className="text-ink-400 hover:text-error">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mb-space-2 text-[12.5px] text-error">{error}</p>}
      <div className="flex flex-wrap items-end gap-space-2">
        <div>
          <label className="mb-space-1 block text-[11px] font-semibold text-ink-400">Date</label>
          <Input type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} className="w-40" />
        </div>
        <Input placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} className="max-w-[180px]" />
        <Button type="button" size="md" onClick={handleAdd} disabled={adding || !newDate}>
          <Plus size={13} /> {adding ? "Adding…" : "Add downtime"}
        </Button>
      </div>
    </div>
  );
}
