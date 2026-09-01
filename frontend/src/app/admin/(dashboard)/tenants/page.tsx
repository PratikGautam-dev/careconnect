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
    <div className="mx-auto max-w-[1000px]">
      <div className="mb-space-5 flex items-center justify-between">
        <div>
          <p className="text-eyebrow mb-space-1">Platform admin</p>
          <h1 className="text-display">All tenants</h1>
        </div>
        <Button href="/admin/onboard-hospital" variant="secondary">
          Onboard a hospital
        </Button>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <Card className="p-space-4">
        {!tenants ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
        ) : tenants.length === 0 ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">No tenants onboarded yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {tenants.map((t) => (
              <li key={t.id} className="flex items-center justify-between py-space-3">
                <div>
                  <p className="text-[13.5px] font-semibold text-ink-900">{t.name}</p>
                  <p className="text-[12px] text-ink-600">
                    #{t.id} · {t.whatsapp_phone_number_id || "no phone_number_id set"} · {TIER_LABELS[t.data_tier] || t.data_tier}
                  </p>
                </div>
                <div className="flex items-center gap-space-3">
                  <span
                    className={cn(
                      "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                      t.is_active ? "bg-success-tint text-success" : "bg-black/[0.05] text-ink-400",
                    )}
                  >
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                  <Link
                    href={`/admin/tenants/${t.id}`}
                    className="flex items-center gap-1 text-[12.5px] font-semibold text-brand-600 hover:underline"
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
        <p className="text-[13px] text-ink-600">
          Google accounts that have signed in but don&apos;t own a hospital yet.
        </p>
      </div>
      <Card className="p-space-4">
        {!stalledSignups ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
        ) : stalledSignups.length === 0 ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">
            Nobody — every signed-in account owns at least one hospital.
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {stalledSignups.map((u) => (
              <li key={u.id} className="flex items-center justify-between py-space-3">
                <div>
                  <p className="text-[13.5px] font-semibold text-ink-900">{u.name || u.email}</p>
                  {u.name && <p className="text-[12px] text-ink-600">{u.email}</p>}
                </div>
                <span className="text-[12px] text-ink-400">Signed in {formatDate(u.created_at)}</span>
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
