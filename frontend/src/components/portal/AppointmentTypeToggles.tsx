"use client";

import { Badge } from "@/components/ui/Badge";
import { Switch } from "@/components/ui/Switch";
import { useAppointmentTypes } from "@/hooks/useAppointmentTypes";

/** Portal-level half of the appointment-type allow-list (admin/tenants_api.py's
 * new "Appointment types" section on the edit-tenant page controls is_allowed
 * per tenant; this is where the tenant's own staff flip is_active within that
 * whitelist -- e.g. turning Daycare on after the platform admin has allowed
 * it). A type the platform admin hasn't allowed shows greyed out with no
 * switch at all, rather than one that would just 400 on click. */
export function AppointmentTypeToggles({ canManage }: { canManage: boolean }) {
  const { types, error, pendingId, toggleActive } = useAppointmentTypes();

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
                <Switch
                  checked={type.is_active}
                  onChange={() => toggleActive(type)}
                  disabled={pendingId === type.id || !canManage}
                  aria-label={`Toggle ${type.label}`}
                />
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
