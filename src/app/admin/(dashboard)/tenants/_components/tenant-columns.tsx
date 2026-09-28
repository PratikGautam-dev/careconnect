"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Eye } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import type { Tenant } from "@/hooks/useTenants";
import { formatDate } from "@/lib/formatDate";

export const TENANT_TYPE_LABELS: Record<string, string> = {
  hospital: "Hospital",
  clinic: "Clinic",
};

type CreateTenantColumnsOptions = {
  // hospital_id -> its subscription's real plan name (admin/subscriptions_api.py,
  // e.g. "Starter"/"Professional") -- null/missing means never assigned a
  // plan, not the hospital's data_tier (Tier 1/2/3, a data-connection detail
  // shown nowhere on this table).
  planNameByHospitalId: Map<number, string | null>;
};

/** Column defs for the /admin/tenants Hospital Directory table -- every
 * column here is a real hospitals-table field (Tenant type, useTenants.ts's
 * own docstring has where each one comes from); there's no per-row mock
 * data (subscription/onboarding-stage/renewal-date columns from the target
 * design are left off rather than fabricated -- see the page's own
 * docstring for the aggregate-level cards that DO carry mock data). */
export function createTenantColumns({
  planNameByHospitalId,
}: CreateTenantColumnsOptions): ColumnDef<Tenant>[] {
  return [
    {
      id: "name",
      header: "Tenant Name",
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
        <span className="text-ink-600">
          {planNameByHospitalId.get(row.original.id) || "Unassigned"}
        </span>
      ),
    },
    {
      id: "status",
      header: "Tenant Status",
      cell: ({ row }) => (
        <Badge tone={row.original.is_active ? "success" : "neutral"}>
          {row.original.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      id: "tenant_type",
      header: "Tenant Type",
      cell: ({ row }) => (
        <span className="text-ink-600">
          {TENANT_TYPE_LABELS[row.original.tenant_type] || row.original.tenant_type}
        </span>
      ),
    },
    {
      id: "onboarded",
      header: "Onboarded",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">
          {formatDate(row.original.created_at)}
        </span>
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
