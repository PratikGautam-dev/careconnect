"use client";

import { useState } from "react";
import { Search, Users as UsersIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { useStaffSummary } from "@/hooks/useStaffSummary";

const TIER_LABELS: Record<string, string> = { tier1: "Tier 1", tier2: "Tier 2", tier3: "Tier 3" };

function UsersOverview() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [tierFilter, setTierFilter] = useState<"" | "tier1" | "tier2" | "tier3">("");
  const [statusFilter, setStatusFilter] = useState<"" | "active" | "inactive">("");
  const { hospitals, error } = useStaffSummary(search);

  const filtered = (hospitals ?? []).filter((h) => {
    if (tierFilter && h.data_tier !== tierFilter) return false;
    if (statusFilter && (statusFilter === "active") !== h.is_active) return false;
    return true;
  });

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Users</h1>
        <p className="text-ink-600 text-[13px]">
          Staff headcount by hospital. Pick a hospital to see its staff list — read-only here, edit
          a person&apos;s role or active status from that hospital&apos;s own Staff page.
        </p>
      </div>

      <div className="mb-space-4 gap-space-2 sm:gap-space-3 flex flex-col sm:flex-row sm:items-center">
        <div className="relative w-full flex-1 sm:max-w-[320px]">
          <Search
            size={15}
            className="left-space-3 text-ink-400 absolute top-1/2 -translate-y-1/2"
          />
          <Input
            placeholder="Search by hospital name"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="gap-space-2 flex">
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value as typeof tierFilter)}
            className="border-line bg-card px-space-3 text-ink-900 h-10 flex-1 rounded-md border text-[13.5px] sm:flex-none"
          >
            <option value="">All tiers</option>
            <option value="tier1">Tier 1</option>
            <option value="tier2">Tier 2</option>
            <option value="tier3">Tier 3</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
            className="border-line bg-card px-space-3 text-ink-900 h-10 flex-1 rounded-md border text-[13.5px] sm:flex-none"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {!hospitals ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          No hospitals match this filter.
        </p>
      ) : (
        <div className="gap-space-3 grid grid-cols-1 md:grid-cols-2">
          {filtered.map((h) => (
            <Card
              key={h.id}
              elevation="interactive"
              className="p-space-4"
              onClick={() => router.push(`/admin/users/${h.id}`)}
            >
              <div className="mb-space-3 flex items-start justify-between">
                <div>
                  <p className="text-ink-900 text-[14.5px] font-semibold">{h.name}</p>
                  <p className="text-ink-600 text-[12px]">
                    {TIER_LABELS[h.data_tier] || h.data_tier}
                  </p>
                </div>
                <span
                  className={cn(
                    "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                    h.is_active ? "bg-success-tint text-success" : "text-ink-400 bg-black/[0.05]",
                  )}
                >
                  {h.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <div className="gap-x-space-4 gap-y-space-2 border-line pt-space-3 flex flex-wrap items-center border-t">
                {h.role_breakdown.map((r) => (
                  <div key={r.role_id} className="gap-space-1.5 flex items-center">
                    <UsersIcon size={14} className="text-ink-400" />
                    <span className="text-ink-700 text-[13px]">
                      {r.count} {r.role_name}
                      {r.count === 1 ? "" : "s"}
                    </span>
                  </div>
                ))}
                <span className="text-ink-400 ml-auto text-[12px] font-semibold">
                  {h.total_count} total
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default function UsersPage() {
  return <UsersOverview />;
}
