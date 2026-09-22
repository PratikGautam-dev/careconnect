import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

/** Whole-day procedure unavailability (maintenance, downtime) -- the
 * procedure-scoped sibling of useTestLeave, same date-keyed CRUD, pointed at
 * /api/portal/procedures/{procedureId}/leave... instead of
 * /api/portal/diagnostic-tests/.... */
export function useProcedureLeave(procedureId: number) {
  const [newDate, setNewDate] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: dates, refetch } = useQuery({
    queryKey: ["portal-procedure-leave", procedureId],
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/procedures/${procedureId}/leave`);
      if (!result.ok) return [];
      return (result.data as { leave_dates: string[] }).leave_dates;
    },
  });

  const addMutation = useMutation({
    mutationFn: async ({ date, reason }: { date: string; reason: string }) => {
      const result = await portalFetch(`/api/portal/procedures/${procedureId}/leave`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, reason }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function handleAdd() {
    if (!newDate) return;
    setError(null);
    try {
      await addMutation.mutateAsync({ date: newDate, reason });
      toast.success("Downtime added");
      setNewDate("");
      setReason("");
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't add downtime", message);
    }
  }

  const deleteMutation = useMutation({
    mutationFn: async (date: string) => {
      const result = await portalFetch(`/api/portal/procedures/${procedureId}/leave/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function handleDelete(date: string) {
    try {
      await deleteMutation.mutateAsync(date);
      toast.success("Downtime removed");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      toast.error("Couldn't remove downtime", message);
    }
    refetch();
  }

  return {
    dates: dates ?? null,
    error,
    newDate,
    setNewDate,
    reason,
    setReason,
    adding: addMutation.isPending,
    handleAdd,
    handleDelete,
  };
}
