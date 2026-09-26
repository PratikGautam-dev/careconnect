import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

export type CursorPageResult<TItem> = {
  entries: TItem[];
  next_cursor: number | null;
  has_more: boolean;
};

/** Generic keyset-pagination state machine, shared by every /portal/*
 * list that pages via before_id/next_cursor/has_more (Doctors, Staff,
 * Patients today) -- same shape as useAuditLogPage.ts's own cursor-stack
 * logic, pulled out here so a fourth list doesn't have to re-derive it.
 * (useAuditLogPage.ts itself isn't rebuilt on top of this -- it's already
 * shipped and tested against real data; not worth the regression risk to
 * dedupe retroactively.)
 *
 * `fetchPage` returns the FULL raw response (not just entries/next_cursor/
 * has_more) since some of these routes bundle extra hospital-wide data
 * alongside the paginated list (Doctors' `departments`/`on_leave_today_
 * count`) -- callers read those off `data` directly. `filters` can be any
 * shape; resetting to page 1 happens the instant it (or pageSize) changes,
 * in the same render (not a useEffect) -- see the `if (key !== lastKey)`
 * block below, same "adjust state during render" pattern useAuditLogPage.ts
 * uses instead of a mirror-props-into-state effect. */
export function useCursorPage<TFilters, TResponse extends CursorPageResult<unknown>>(
  queryKeyPrefix: string,
  fetchPage: (filters: TFilters, beforeId: number | null, limit: number) => Promise<TResponse>,
  filters: TFilters,
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
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: [queryKeyPrefix, key, cursor],
    queryFn: () => fetchPage(filters, cursor, pageSize),
    enabled,
  });

  const goNext = () => {
    if (!data?.has_more || data.next_cursor === null) return;
    setCursorStack((stack) => [...stack.slice(0, pageIndex + 1), data.next_cursor]);
    setPageIndex((i) => i + 1);
  };
  const goPrev = () => setPageIndex((i) => Math.max(0, i - 1));
  // Re-fetches the CURRENT page in place (not a reset back to page 1) --
  // what a mutation (create/update/toggle-active) should trigger, since
  // "I just edited a row on page 2" shouldn't bounce the caller back to
  // page 1 to see it reflected.
  const reload = () => queryClient.invalidateQueries({ queryKey: [queryKeyPrefix] });

  return {
    data,
    isLoading,
    error: error ? (error as Error).message : null,
    hasNext: !!data?.has_more,
    hasPrev: pageIndex > 0,
    pageNumber: pageIndex + 1,
    goNext,
    goPrev,
    reload,
  };
}
