import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

/** Diagnostic/Lab Phase 2: whole-day resource unavailability (maintenance,
 * downtime) -- simpler than useDoctorLeave's id-based CRUD since the backend
 * here keys leave by date directly, one date at a time. */
export function useResourceLeave(resourceId: string) {
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
      if (!result.unauthorized) toast.error("Couldn't add downtime", result.error);
      return;
    }
    toast.success("Downtime added");
    setNewDate("");
    setReason("");
    load();
  }

  async function handleDelete(date: string) {
    const result = await portalFetch(`/api/portal/diagnostic-resources/${resourceId}/leave/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
    if (result.ok) {
      toast.success("Downtime removed");
    } else if (!result.unauthorized) {
      toast.error("Couldn't remove downtime", result.error);
    }
    load();
  }

  return { dates, error, newDate, setNewDate, reason, setReason, adding, handleAdd, handleDelete };
}
