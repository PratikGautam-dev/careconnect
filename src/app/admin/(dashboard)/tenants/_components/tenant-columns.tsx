"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Eye } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import type { Tenant } from "@/hooks/useTenants";
import { formatDate } from "@/lib/formatDate";

export const TIER_LABELS: Record<string, string> = {
  tier1: "Tier 1",
  tier2: "Tier 2",
  tier3: "Tier 3",
};

type CreateTenantColumnsOptions = {
  selectedIds: Set<number>;
  onToggle: (id: number) => void;
  onToggleAll: (checked: boolean) => void;
  allSelected: boolean;
};

/** Column defs for the /admin/tenants Hospital Directory table -- every
 * column here is a real hospitals-table field (Tenant type, useTenants.ts's
 * own docstring has where each one comes from); there's no per-row mock
 * data (subscription/onboarding-stage/renewal-date columns from the target
 * design are left off rather than fabricated -- see the page's own
 * docstring for the aggregate-level cards that DO carry mock data). */
export function createTenantColumns({
  selectedIds,
  onToggle,
  onToggleAll,
  allSelected,
}: CreateTenantColumnsOptions): ColumnDef<Tenant>[] {
  return [
    {
      id: "select",
      header: () => (
        <input
          type="checkbox"
          checked={allSelected}
          onChange={(e) => onToggleAll(e.target.checked)}
          aria-label="Select all"
          className="accent-brand-600 h-4 w-4"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedIds.has(row.original.id)}
          onChange={(e) => {
            e.stopPropagation();
            onToggle(row.original.id);
          }}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${row.original.name}`}
          className="accent-brand-600 h-4 w-4"
        />
      ),
    },
    {
      id: "name",
      header: "Hospital Name",
      cell: ({ row }) => (
        <div>
          <p className="text-ink-900 font-semibold">{row.original.name}</p>
          <p className="text-ink-400 text-[11.5px]">#{row.original.id}</p>
        </div>
      ),
    },
    {
      id: "location",
      header: "Location",
      cell: ({ row }) => (
        <span className="text-ink-600">{row.original.contact_address || "—"}</span>
      ),
    },
    {
      id: "plan",
      header: "Plan",
      cell: ({ row }) => (
        <span className="text-ink-600">{TIER_LABELS[row.original.data_tier] || row.original.data_tier}</span>
      ),
    },
    {
      id: "status",
      header: "Subscription Status",
      cell: ({ row }) => (
        <Badge tone={row.original.is_active ? "success" : "neutral"}>
          {row.original.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      id: "whatsapp",
      header: "WhatsApp",
      cell: ({ row }) => (
        <Badge tone={row.original.whatsapp_phone_number_id ? "success" : "neutral"}>
          {row.original.whatsapp_phone_number_id ? "Enabled" : "Disabled"}
        </Badge>
      ),
    },
    {
      id: "onboarded",
      header: "Onboarded",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">{formatDate(row.original.created_at)}</span>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <Link
          href={`/admin/tenants/${row.original.id}`}
          onClick={(e) => e.stopPropagation()}
          className="text-brand-600 gap-space-1 inline-flex items-center text-[12.5px] font-semibold hover:underline"
        >
          <Eye size={13} /> View
        </Link>
      ),
    },
  ];
}
