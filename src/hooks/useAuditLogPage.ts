import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

export type AuditEntry = {
  id: number;
  actor_level: string;
  hospital_id: number | null;
  hospital_name?: string | null;
  actor_label: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  created_at: string;
};

export type AuditLogPageResponse = {
  entries: AuditEntry[];
  next_cursor: number | null;
  has_more: boolean;
};

export type AuditLogFilters = {
  action: string;
  entity_type: string;
  date_from: string;
  date_to: string;
  search: string;
  hospital_id: string;
  actor_level: "" | "platform_admin" | "portal";
};

export const EMPTY_AUDIT_LOG_FILTERS: AuditLogFilters = {
  action: "",
  entity_type: "",
  date_from: "",
  date_to: "",
  search: "",
  hospital_id: "",
  actor_level: "",
};

/** Turns a filter set into the query string both audit-log routes
 * (/api/admin/audit-log, /api/portal/audit-log) understand -- shared here
 * so the admin and portal pages can't drift on param names even though each
 * only ever populates a subset of AuditLogFilters (portal never sets
 * hospital_id/actor_level, since its route hardcodes actor_level="portal"
 * server-side regardless of what's sent). */
export function auditLogSearchParams(
  filters: AuditLogFilters,
  beforeId: number | null,
  limit: number,
) {
  const params = new URLSearchParams();
  if (filters.action) params.set("action", filters.action);
  if (filters.entity_type) params.set("entity_type", filters.entity_type);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.search) params.set("search", filters.search);
  if (filters.hospital_id) params.set("hospital_id", filters.hospital_id);
  if (filters.actor_level) params.set("actor_level", filters.actor_level);
  if (beforeId !== null) params.set("before_id", String(beforeId));
  params.set("limit", String(limit));
  return params;
}

/** Cursor-paginated audit-log reader shared by the admin and portal audit
 * log pages -- `fetchPage` is the one thing each caller supplies (points at
 * its own endpoint/auth), everything else (filter-driven reset, the
 * cursor stack that makes "Previous" work, has-more/loading state) is
 * identical between them.
 *
 * `cursorStack[i]` is the `before_id` that was used to fetch page i+1 (so
 * cursorStack[0] is always null -- page 1 has no cursor). Moving forward
 * pushes the just-fetched page's own next_cursor so "Previous" can pop
 * back to a cursor already known to produce that earlier page, without
 * re-deriving it or caching whole pages by hand -- react-query's own cache
 * (keyed on [...filters, cursor]) already serves an already-visited page
 * instantly from memory when you page back into it.
 *
 * Resets to page 1 the instant filters/pageSize change, in the same render
 * (not a useEffect) -- see the `if (key !== lastKey)` block below: this is
 * the same "adjust state during render" pattern already used elsewhere in
 * this app (e.g. ProcedureSlotManager) instead of a mirror-props-into-state
 * effect, which is both simpler and avoids react-hooks/set-state-in-effect. */
export function useAuditLogPage(
  fetchPage: (params: URLSearchParams) => Promise<AuditLogPageResponse>,
  filters: AuditLogFilters,
  pageSize: number,
  enabled: boolean = true,
) {
  const [cursorStack, setCursorStack] = useState<(number | null)[]>([null]);
  const [pageIndex, setPageIndex] = useState(0);

  const key = JSON.stringify({ filters, pageSize });
  const [lastKey, setLastKey] = useState(key);
  if (key !== lastKey) {
    setLastKey(key);
    setCursorStack([null]);
    setPageIndex(0);
  }

  const cursor = cursorStack[pageIndex] ?? null;

  const { data, isLoading, error } = useQuery({
    queryKey: ["audit-log-page", key, cursor],
    queryFn: () => fetchPage(auditLogSearchParams(filters, cursor, pageSize)),
    enabled,
  });

  const goNext = () => {
    if (!data?.has_more || data.next_cursor === null) return;
    setCursorStack((stack) => [...stack.slice(0, pageIndex + 1), data.next_cursor]);
    setPageIndex((i) => i + 1);
  };
  const goPrev = () => setPageIndex((i) => Math.max(0, i - 1));

  return {
    entries: data?.entries ?? [],
    isLoading,
    error: error ? (error as Error).message : null,
    hasNext: !!data?.has_more,
    hasPrev: pageIndex > 0,
    pageNumber: pageIndex + 1,
    goNext,
    goPrev,
  };
}
