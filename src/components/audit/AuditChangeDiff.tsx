"use client";

import { useState } from "react";
import type { AuditEntry } from "@/hooks/useAuditLogPage";

const COLLAPSED_FIELD_LIMIT = 5;

function displayValue(v: unknown): string {
  if (v === undefined) return "—";
  if (v === null) return "null";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

/** One line per changed field ("field: old → new"), not the old
 * formatAuditChanges()'s single JSON.stringify-per-field string squashed
 * onto one line -- before_value/after_value are already "changed fields
 * only" (db/repositories/audit_logs.py's own record_audit_log() contract),
 * so every key here IS a real change worth its own line. A field present
 * only in after_value (a create) shows as "— → new"; only in before_value
 * (a delete/clear) shows as "old → —".
 *
 * Collapsed to COLLAPSED_FIELD_LIMIT lines behind a "+N more" toggle once a
 * row has more changed fields than that (a full subscription/plan update
 * routinely touches 10+ columns in one entry) -- otherwise a single such
 * row dwarfs the rest of that page's table, forcing a long scroll past
 * mostly-empty cells in every other column just to reach the next row. */
export function AuditChangeDiff({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const keys = Array.from(
    new Set([...Object.keys(entry.before_value || {}), ...Object.keys(entry.after_value || {})]),
  );
  if (keys.length === 0) return <span className="text-ink-400">—</span>;

  const visibleKeys = expanded ? keys : keys.slice(0, COLLAPSED_FIELD_LIMIT);
  const hiddenCount = keys.length - visibleKeys.length;

  return (
    <div className="gap-space-1 flex flex-col">
      {visibleKeys.map((key) => {
        const before = entry.before_value?.[key];
        const after = entry.after_value?.[key];
        return (
          <div key={key} className="gap-space-1 flex flex-wrap items-baseline text-[12.5px]">
            <span className="text-ink-900 font-medium">{key}:</span>
            <span className="text-ink-500 line-through decoration-1">{displayValue(before)}</span>
            <span className="text-ink-400">→</span>
            <span className="text-ink-900">{displayValue(after)}</span>
          </div>
        );
      })}
      {hiddenCount > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="text-brand-600 w-fit text-[12px] font-semibold hover:underline"
        >
          +{hiddenCount} more field{hiddenCount === 1 ? "" : "s"}
        </button>
      )}
      {expanded && keys.length > COLLAPSED_FIELD_LIMIT && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="text-ink-400 w-fit text-[12px] font-semibold hover:underline"
        >
          Show less
        </button>
      )}
    </div>
  );
}
