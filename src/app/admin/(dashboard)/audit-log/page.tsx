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
      if (before !== undefined && after !== undefined)
        return `${key}: ${JSON.stringify(before)} → ${JSON.stringify(after)}`;
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
    <div>
      <div className="mb-space-5 gap-space-3 flex flex-col items-start sm:flex-row sm:items-center sm:justify-between">
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
          className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px] sm:w-auto"
        >
          <option value="">All levels</option>
          <option value="platform_admin">Platform only</option>
          <option value="portal">Portal only</option>
        </select>
      </div>

      {hospitalIdParam && (
        <Link
          href="/admin/audit-log"
          className="mb-space-4 text-brand-600 inline-block text-[12.5px] font-semibold hover:underline"
        >
          Clear tenant filter — show every tenant
        </Link>
      )}

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <Card className="p-space-4">
        {!entries ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="py-space-4 text-ink-400 text-center text-[13px]">
            No activity recorded yet.
          </p>
        ) : (
          <ul className="divide-line divide-y">
            {entries.map((entry) => (
              <li key={entry.id} className="py-space-3 text-[12.5px]">
                <div className="gap-space-1 sm:gap-space-3 flex flex-col sm:flex-row sm:items-center sm:justify-between">
                  <div className="gap-space-2 flex flex-wrap items-center">
                    <span className="text-ink-900 font-medium">{entry.action}</span>
                    <span
                      className={cn(
                        "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                        entry.actor_level === "platform_admin"
                          ? "bg-brand-50 text-brand-700"
                          : "text-ink-600 bg-black/[0.05]",
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
                  <span className="text-ink-400 shrink-0">{entry.created_at}</span>
                </div>
                {formatAuditChanges(entry) && (
                  <p className="mt-space-1 text-ink-600">{formatAuditChanges(entry)}</p>
                )}
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
