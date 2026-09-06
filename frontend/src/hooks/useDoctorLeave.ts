import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type LeaveEntry = { id: number; date: string; reason: string | null };

/** Loads + owns every mutation on one doctor's leave-date list.
 * Item 10 (Spec.md Section 0): From/To range with one Confirm, replacing
 * the old one-date-at-a-time add. A single date is just a range where
 * from === to, so this fully replaces the old single-date form rather
 * than living alongside it. */
export function useDoctorLeave(doctorId: string) {
  const [leave, setLeave] = useState<LeaveEntry[] | null>(null);
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
      if (!result.unauthorized) toast.error("Couldn't add leave", result.error);
      return;
    }
    toast.success("Leave added");
    setFromDate("");
    setToDate("");
    setReason("");
    load();
  }

  async function handleDelete(leaveId: number) {
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/leave/${leaveId}/delete`, { method: "POST" });
    if (result.ok) {
      toast.success("Leave removed");
    } else if (!result.unauthorized) {
      toast.error("Couldn't remove leave", result.error);
    }
    load();
  }

  return {
    leave, error,
    fromDate, setFromDate, toDate, setToDate, reason, setReason, adding,
    handleAdd, handleDelete,
  };
}
