import { useCallback, useEffect, useState } from "react";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type AppointmentTypeRow = { id: string; label: string; is_active: boolean; is_allowed: boolean };

/** Loads + toggles this hospital's appointment-type allow-list (admin/
 * tenants_api.py's "Appointment types" section controls is_allowed per
 * tenant; this is where the tenant's own staff flip is_active within that
 * whitelist -- e.g. turning Daycare on after the platform admin has allowed
 * it). */
export function useAppointmentTypes() {
  const [types, setTypes] = useState<AppointmentTypeRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/appointment-types");
    if (!result.ok) {
      setTypes(null);
      return;
    }
    setTypes((result.data as { appointment_types: AppointmentTypeRow[] }).appointment_types);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleActive(type: AppointmentTypeRow) {
    setPendingId(type.id);
    setError(null);
    const result = await portalFetch(`/api/portal/appointment-types/${type.id}/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !type.is_active }),
    });
    setPendingId(null);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — please log in again." : result.error);
      if (!result.unauthorized) toast.error("Couldn't update appointment type", result.error);
      return;
    }
    toast.success(type.is_active ? `${type.label} deactivated` : `${type.label} activated`);
    load();
  }

  return { types, error, pendingId, toggleActive };
}
