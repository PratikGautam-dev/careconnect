"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { useAuditLog, type AuditEntry } from "@/hooks/useAuditLog";

function formatAuditChanges(entry: AuditEntry): string {
  const keys = new Set([
    ...Object.keys(entry.before_value || {}),
    ...Object.keys(entry.after_value || {}),
  ]);
  if (keys.size === 0) return "";
  return Array.from(keys)
    .map((key) => {
      const before = entry.before_value?.[key];
      const after = entry.after_value?.[key];
      if (before !== undefined && after !== undefined) return `${key}: ${JSON.stringify(before)} → ${JSON.stringify(after)}`;
      if (after !== undefined) return `${key}: ${JSON.stringify(after)}`;
      return `${key}: ${JSON.stringify(before)}`;
    })
    .join(", ");
}

function AuditLogList() {
  // ?hospital_id=X narrows this cross-tenant view down to one tenant's own
  // history -- what the edit-tenant page's own embedded section links out
  // to, so "view full history" from a tenant lands here pre-filtered
  // instead of duplicating that list's rendering in two places.
  const searchParams = useSearchParams();
  const hospitalIdParam = searchParams.get("hospital_id");

  const [levelFilter, setLevelFilter] = useState<"" | "platform_admin" | "portal">("");
  const { entries, error } = useAuditLog(hospitalIdParam, levelFilter);

  return (
    <div className="mx-auto max-w-[1000px]">
      <div className="mb-space-5 flex items-center justify-between">
        <div>
          <p className="text-eyebrow mb-space-1">Platform admin</p>
          <h1 className="text-display">
            Audit log
            {hospitalIdParam && <span className="text-ink-400"> · tenant #{hospitalIdParam}</span>}
          </h1>
        </div>
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value as "" | "platform_admin" | "portal")}
          className="h-10 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
        >
          <option value="">All levels</option>
          <option value="platform_admin">Platform only</option>
          <option value="portal">Portal only</option>
        </select>
      </div>

      {hospitalIdParam && (
        <Link href="/admin/audit-log" className="mb-space-4 inline-block text-[12.5px] font-semibold text-brand-600 hover:underline">
          Clear tenant filter — show every tenant
        </Link>
      )}

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <Card className="p-space-4">
        {!entries ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">No activity recorded yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {entries.map((entry) => (
              <li key={entry.id} className="py-space-3 text-[12.5px]">
                <div className="flex items-center justify-between gap-space-3">
                  <div className="flex items-center gap-space-2">
                    <span className="font-medium text-ink-900">{entry.action}</span>
                    <span
                      className={cn(
                        "rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                        entry.actor_level === "platform_admin" ? "bg-brand-50 text-brand-700" : "bg-black/[0.05] text-ink-600",
                      )}
                    >
                      {entry.actor_level === "platform_admin" ? "Platform" : "Portal"}
                    </span>
                    {entry.hospital_id && (
                      <Link
                        href={`/admin/tenants/${entry.hospital_id}`}
                        className="text-brand-600 hover:underline"
                      >
                        {entry.hospital_name || `Tenant #${entry.hospital_id}`}
                      </Link>
                    )}
                  </div>
                  <span className="shrink-0 text-ink-400">{entry.created_at}</span>
                </div>
                {formatAuditChanges(entry) && <p className="mt-space-1 text-ink-600">{formatAuditChanges(entry)}</p>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export default function AuditLogPage() {
  return (
    <Suspense>
      <AuditLogList />
    </Suspense>
  );
}
