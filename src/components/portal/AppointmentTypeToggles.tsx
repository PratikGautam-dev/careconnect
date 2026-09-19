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
      {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}
      <ul className="divide-line divide-y">
        {types.map((type) => (
          <li
            key={type.id}
            className="gap-space-2 py-space-2 sm:gap-space-3 flex flex-col sm:flex-row sm:items-center sm:justify-between"
          >
            <p
              className={`text-[13.5px] font-semibold ${type.is_allowed ? "text-ink-900" : "text-ink-400"}`}
            >
              {type.label}
            </p>
            {!type.is_allowed ? (
              <span className="text-ink-400 text-[12px]">
                Not enabled for your plan — contact support
              </span>
            ) : (
              <div className="gap-space-3 flex items-center">
                <Badge tone={type.is_active ? "success" : "neutral"}>
                  {type.is_active ? "Active" : "Inactive"}
                </Badge>
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
