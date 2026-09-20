import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type AppointmentTypeRow = {
  id: string;
  label: string;
  is_active: boolean;
  is_allowed: boolean;
};

/** Loads + toggles this hospital's appointment-type allow-list (admin/
 * tenants_api.py's "Appointment types" section controls is_allowed per
 * tenant; this is where the tenant's own staff flip is_active within that
 * whitelist -- e.g. turning Daycare on after the platform admin has allowed
 * it). */
export function useAppointmentTypes() {
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const { data: types, refetch } = useQuery({
    queryKey: ["portal-appointment-types"],
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/appointment-types");
      if (!result.ok) return null;
      return (result.data as { appointment_types: AppointmentTypeRow[] }).appointment_types;
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ typeId, isActive }: { typeId: string; isActive: boolean }) => {
      const result = await portalFetch(`/api/portal/appointment-types/${typeId}/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function toggleActive(type: AppointmentTypeRow) {
    setPendingId(type.id);
    setError(null);
    try {
      await toggleActiveMutation.mutateAsync({ typeId: type.id, isActive: !type.is_active });
      toast.success(type.is_active ? `${type.label} deactivated` : `${type.label} activated`);
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      toast.error("Couldn't update appointment type", message);
    } finally {
      setPendingId(null);
    }
  }

  return { types: types ?? null, error, pendingId, toggleActive };
}
