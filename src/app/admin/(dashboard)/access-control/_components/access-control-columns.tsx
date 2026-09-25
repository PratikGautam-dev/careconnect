"use client";

import type { ColumnDef } from "@tanstack/react-table";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Switch } from "@/components/ui/Switch";

export type CapabilityRow = {
  key: string;
  label: string;
  icon: LucideIcon;
  enabled: boolean;
  inPlan: boolean;
};

type CreateAccessControlColumnsOptions = {
  onToggle: (key: string, checked: boolean) => void;
};

/** Column defs for Access Control's "Hospital Feature & Menu Access" table
 * -- every row is a real admin_capabilities key (portal/capabilities.py),
 * same DataTable component the portal's own list pages use rather than a
 * hand-rolled <table>. */
export function createAccessControlColumns({
  onToggle,
}: CreateAccessControlColumnsOptions): ColumnDef<CapabilityRow>[] {
  return [
    {
      id: "module",
      header: "Module / Feature",
      cell: ({ row }) => {
        const Icon = row.original.icon;
        return (
          <div className="gap-space-2 flex items-center">
            <Icon size={15} className="text-brand-600 shrink-0" />
            <span className="text-ink-900 font-semibold">{row.original.label}</span>
          </div>
        );
      },
    },
    {
      id: "menuVisible",
      header: () => <span className="block text-center">Menu Visible</span>,
      cell: ({ row }) => (
        <div className="text-center">
          <span className={row.original.enabled ? "text-success" : "text-ink-300"}>●</span>
        </div>
      ),
    },
    {
      id: "featureEnabled",
      header: () => <span className="block text-center">Feature Enabled</span>,
      cell: ({ row }) => (
        <div className="flex justify-center">
          <Switch
            checked={row.original.enabled}
            onChange={() => onToggle(row.original.key, !row.original.enabled)}
            size="sm"
            aria-label={`Toggle ${row.original.label}`}
          />
        </div>
      ),
    },
    {
      id: "includedInPlan",
      header: () => <span className="block text-center">Included in Plan</span>,
      cell: ({ row }) => (
        <div className="text-ink-600 text-center">{row.original.inPlan ? "Yes" : "—"}</div>
      ),
    },
    {
      id: "customOverride",
      header: () => <span className="block text-center">Custom Override</span>,
      cell: ({ row }) => (
        <div className="text-center">
          {row.original.enabled !== row.original.inPlan ? (
            <Badge tone="clay">Overridden</Badge>
          ) : (
            <span className="text-ink-300">—</span>
          )}
        </div>
      ),
    },
  ];
}
