"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { portalFetch } from "@/lib/portalAuth";

type LeaveEntry = { id: number; date: string; reason: string | null };

export function DoctorLeaveManager({ doctorId }: { doctorId: string }) {
  const [leave, setLeave] = useState<LeaveEntry[] | null>(null);
  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/leave`);
    if (result.ok) setLeave((result.data as { leave: LeaveEntry[] }).leave);
  }, [doctorId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd() {
    if (!date) return;
    setAdding(true);
    await portalFetch(`/api/portal/doctors/${doctorId}/leave`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, reason }),
    });
    setAdding(false);
    setDate("");
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
      <div className="flex flex-wrap items-center gap-space-2">
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" />
        <Input placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} className="max-w-[180px]" />
        <Button type="button" size="md" onClick={handleAdd} disabled={adding || !date}>
          <Plus size={13} /> Add leave
        </Button>
      </div>
    </div>
  );
}
