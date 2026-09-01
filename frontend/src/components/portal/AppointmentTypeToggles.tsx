"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { portalFetch } from "@/lib/portalAuth";

type AppointmentTypeRow = { id: string; label: string; is_active: boolean; is_allowed: boolean };

/** Portal-level half of the appointment-type allow-list (admin/tenants_api.py's
 * new "Appointment types" section on the edit-tenant page controls is_allowed
 * per tenant; this is where the tenant's own staff flip is_active within that
 * whitelist -- e.g. turning Daycare on after the platform admin has allowed
 * it). A type the platform admin hasn't allowed shows greyed out with no
 * switch at all, rather than one that would just 400 on click. */
export function AppointmentTypeToggles({ canManage }: { canManage: boolean }) {
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
      return;
    }
    load();
  }

  if (types === null) return null;

  return (
    <div>
      {error && <p className="mb-space-3 text-[12.5px] font-medium text-error">{error}</p>}
      <ul className="divide-y divide-line">
        {types.map((type) => (
          <li key={type.id} className="flex flex-col gap-space-2 py-space-2 sm:flex-row sm:items-center sm:justify-between sm:gap-space-3">
            <p className={`text-[13.5px] font-semibold ${type.is_allowed ? "text-ink-900" : "text-ink-400"}`}>
              {type.label}
            </p>
            {!type.is_allowed ? (
              <span className="text-[12px] text-ink-400">Not enabled for your plan — contact support</span>
            ) : (
              <div className="flex items-center gap-space-3">
                <Badge tone={type.is_active ? "success" : "neutral"}>{type.is_active ? "Active" : "Inactive"}</Badge>
                <button
                  type="button"
                  onClick={() => toggleActive(type)}
                  disabled={pendingId === type.id || !canManage}
                  role="switch"
                  aria-checked={type.is_active}
                  className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 ${
                    type.is_active ? "bg-brand-600" : "bg-line"
                  } ${pendingId === type.id ? "opacity-60" : ""}`}
                >
                  <span
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ${
                      type.is_active ? "translate-x-[22px]" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
