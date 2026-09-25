"use client";

import type { ColumnDef } from "@tanstack/react-table";
import type { LucideIcon } from "lucide-react";
import { Switch } from "@/components/ui/Switch";

export type FeatureRow = {
  key: string;
  label: string;
  icon: LucideIcon;
  enabled: boolean;
};

type CreateFeatureTogglesColumnsOptions = {
  onToggle: (key: string, checked: boolean) => void;
};

/** Column defs for Feature Toggles' "Hospital Feature Toggles" table --
 * every row is a real hospitals.enabled_features key
 * (flows/patient_identity/menu.py's REAL_FEATURES), same DataTable
 * component the portal's own list pages use rather than a hand-rolled
 * <table>. "Included in Plan"/"Custom Override" are always "—" here (see
 * the page's own top comment for why that's honest, not a gap). */
export function createFeatureTogglesColumns({
  onToggle,
}: CreateFeatureTogglesColumnsOptions): ColumnDef<FeatureRow>[] {
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
      cell: () => <div className="text-ink-300 text-center">—</div>,
    },
    {
      id: "customOverride",
      header: () => <span className="block text-center">Custom Override</span>,
      cell: () => <div className="text-ink-300 text-center">—</div>,
    },
  ];
}
