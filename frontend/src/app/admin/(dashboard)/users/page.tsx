"use client";

import { useState } from "react";
import { Search, Stethoscope, UserCog, Users as UsersIcon } from "lucide-react";
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
    <div className="mx-auto max-w-[1000px]">
      <div className="mb-space-5">
        <p className="text-eyebrow mb-space-1">Platform admin</p>
        <h1 className="text-display">Users</h1>
        <p className="text-[13px] text-ink-600">
          Staff headcount by hospital. Pick a hospital to see its staff list — read-only here, edit a
          person&apos;s role or active status from that hospital&apos;s own Staff page.
        </p>
      </div>

      <div className="mb-space-4 flex items-center gap-space-3">
        <div className="relative max-w-[320px] flex-1">
          <Search size={15} className="absolute top-1/2 left-space-3 -translate-y-1/2 text-ink-400" />
          <Input
            placeholder="Search by hospital name"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value as typeof tierFilter)}
          className="h-10 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
        >
          <option value="">All tiers</option>
          <option value="tier1">Tier 1</option>
          <option value="tier2">Tier 2</option>
          <option value="tier3">Tier 3</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          className="h-10 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!hospitals ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No hospitals match this filter.</p>
      ) : (
        <div className="grid grid-cols-1 gap-space-3 sm:grid-cols-2">
          {filtered.map((h) => (
            <Card
              key={h.id}
              elevation="interactive"
              className="p-space-4"
              onClick={() => router.push(`/admin/users/${h.id}`)}
            >
              <div className="mb-space-3 flex items-start justify-between">
                <div>
                  <p className="text-[14.5px] font-semibold text-ink-900">{h.name}</p>
                  <p className="text-[12px] text-ink-600">{TIER_LABELS[h.data_tier] || h.data_tier}</p>
                </div>
                <span
                  className={cn(
                    "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                    h.is_active ? "bg-success-tint text-success" : "bg-black/[0.05] text-ink-400",
                  )}
                >
                  {h.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <div className="flex items-center gap-space-5 border-t border-line pt-space-3">
                <div className="flex items-center gap-space-1.5">
                  <UserCog size={14} className="text-ink-400" />
                  <span className="text-[13px] text-ink-700">{h.admin_count} admin{h.admin_count === 1 ? "" : "s"}</span>
                </div>
                <div className="flex items-center gap-space-1.5">
                  <Stethoscope size={14} className="text-ink-400" />
                  <span className="text-[13px] text-ink-700">{h.doctor_count} doctor{h.doctor_count === 1 ? "" : "s"}</span>
                </div>
                <div className="flex items-center gap-space-1.5">
                  <UsersIcon size={14} className="text-ink-400" />
                  <span className="text-[13px] text-ink-700">
                    {h.receptionist_count} receptionist{h.receptionist_count === 1 ? "" : "s"}
                  </span>
                </div>
                <span className="ml-auto text-[12px] font-semibold text-ink-400">{h.total_count} total</span>
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
