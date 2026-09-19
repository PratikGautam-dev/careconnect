"use client";

import { Pencil } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { useTenants } from "@/hooks/useTenants";

const TIER_LABELS: Record<string, string> = { tier1: "Tier 1", tier2: "Tier 2", tier3: "Tier 3" };

function TenantsList() {
  const { tenants, stalledSignups, error } = useTenants();

  return (
    <div>
      <div className="mb-space-5 gap-space-3 flex flex-col items-start sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-eyebrow mb-space-1">Platform admin</p>
          <h1 className="text-display">All tenants</h1>
        </div>
        <Button href="/admin/onboard-hospital" variant="secondary">
          Onboard a hospital
        </Button>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <Card className="p-space-4">
        {!tenants ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        ) : tenants.length === 0 ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">
            No tenants onboarded yet.
          </p>
        ) : (
          <ul className="divide-line divide-y">
            {tenants.map((t) => (
              <li
                key={t.id}
                className="gap-space-2 py-space-3 flex flex-col sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-ink-900 text-[13.5px] font-semibold">{t.name}</p>
                  <p className="text-ink-600 text-[12px]">
                    #{t.id} · {t.whatsapp_phone_number_id || "no phone_number_id set"} ·{" "}
                    {TIER_LABELS[t.data_tier] || t.data_tier}
                  </p>
                </div>
                <div className="gap-space-3 flex items-center">
                  <span
                    className={cn(
                      "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                      t.is_active ? "bg-success-tint text-success" : "text-ink-400 bg-black/[0.05]",
                    )}
                  >
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                  <Link
                    href={`/admin/tenants/${t.id}`}
                    className="text-brand-600 flex items-center gap-1 text-[12.5px] font-semibold hover:underline"
                  >
                    <Pencil size={13} /> Edit
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="mt-space-7 mb-space-3">
        <p className="text-eyebrow mb-space-1">Follow-up</p>
        <h2 className="text-display !text-[20px]">Signed in, never onboarded</h2>
        <p className="text-ink-600 text-[13px]">
          Google accounts that have signed in but don&apos;t own a hospital yet.
        </p>
      </div>
      <Card className="p-space-4">
        {!stalledSignups ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        ) : stalledSignups.length === 0 ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">
            Nobody — every signed-in account owns at least one hospital.
          </p>
        ) : (
          <ul className="divide-line divide-y">
            {stalledSignups.map((u) => (
              <li
                key={u.id}
                className="gap-space-1 py-space-3 flex flex-col sm:flex-row sm:items-center sm:justify-between sm:gap-0"
              >
                <div>
                  <p className="text-ink-900 text-[13.5px] font-semibold">{u.name || u.email}</p>
                  {u.name && <p className="text-ink-600 text-[12px]">{u.email}</p>}
                </div>
                <span className="text-ink-400 text-[12px]">
                  Signed in {formatDate(u.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default function TenantsPage() {
  return <TenantsList />;
}
