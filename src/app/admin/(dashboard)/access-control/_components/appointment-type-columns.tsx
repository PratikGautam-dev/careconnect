"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import { Switch } from "@/components/ui/Switch";
import type { AppointmentTypeRow } from "@/hooks/useEditTenant";

type CreateAppointmentTypeColumnsOptions = {
  onToggle: (appointmentTypeId: string, isAllowed: boolean) => void;
};

/** Column defs for Access Control's "Appointment Types" tab -- the same
 * real per-hospital allow-list toggler that already lives on
 * /admin/tenants/[id] (POST /api/admin/tenants/{id}/appointment-types/{id}/allowed,
 * useEditTenant.ts's toggleAppointmentTypeAllowed), surfaced here too so an
 * operator doesn't have to leave Access Control to reach it. Same DataTable
 * component every list page uses, not a hand-rolled <table>. */
export function createAppointmentTypeColumns({
  onToggle,
}: CreateAppointmentTypeColumnsOptions): ColumnDef<AppointmentTypeRow>[] {
  return [
    {
      id: "type",
      header: "Appointment Type",
      cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.label}</span>,
    },
    {
      id: "currentlyActive",
      header: () => <span className="block text-center">Currently Active</span>,
      cell: ({ row }) => (
        <div className="text-center">
          <Badge tone={row.original.is_active ? "success" : "neutral"}>
            {row.original.is_active ? "Active" : "Off"}
          </Badge>
        </div>
      ),
    },
    {
      id: "allowed",
      header: () => <span className="block text-center">Allowed</span>,
      cell: ({ row }) => (
        <div className="flex justify-center">
          <Switch
            checked={row.original.is_allowed}
            onChange={() => onToggle(row.original.id, !row.original.is_allowed)}
            size="sm"
            aria-label={`Toggle ${row.original.label}`}
          />
        </div>
      ),
    },
  ];
}
