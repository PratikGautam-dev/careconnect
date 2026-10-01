"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { ExportParams, useCsvExport, useExportHistory } from "@/hooks/useExport";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  exportMutation: ReturnType<typeof useCsvExport>;
  history: ReturnType<typeof useExportHistory>;
  historyPage: number;
  onHistoryPageChange: (page: number) => void;
  exportCap?: number;
  /** Page-specific filters (hospital_id, status, ...) merged into the
   * export request alongside the date range. */
  extraParams?: Record<string, string | undefined>;
  /** false hides the From/To inputs entirely -- for a current-state
   * snapshot export (e.g. Subscriptions) where a date range has nothing
   * meaningful to narrow. Defaults to true. */
  showDateRange?: boolean;
};

const HISTORY_PAGE_SIZE = 10;

export function ExportDialog({
  open,
  onOpenChange,
  title,
  exportMutation,
  history,
  historyPage,
  onHistoryPageChange,
  exportCap,
  extraParams,
  showDateRange = true,
}: Props) {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const handleExport = () => {
    const params: ExportParams = { ...extraParams };
    if (showDateRange) {
      params.dateFrom = dateFrom;
      params.dateTo = dateTo;
    }
    exportMutation.mutate(params);
  };

  const total = history.data?.total ?? 0;
  const hasMore = historyPage * HISTORY_PAGE_SIZE < total;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Export {title}</DialogTitle>

        {showDateRange && (
          <div className="gap-space-3 grid grid-cols-2">
            <Field label="From" className="mb-0">
              <Input
                type="date"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full"
              />
            </Field>
            <Field label="To" className="mb-0">
              <Input
                type="date"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full"
              />
            </Field>
          </div>
        )}
        <Button
          type="button"
          onClick={handleExport}
          disabled={exportMutation.isPending}
          className="mt-space-3 w-full whitespace-nowrap"
        >
          {exportMutation.isPending ? (
            <Loader2 size={15} className="shrink-0 animate-spin" />
          ) : (
            <Download size={15} className="shrink-0" />
          )}
          Export CSV
        </Button>

        {exportMutation.isError && (
          <p className="text-error mt-space-2 text-[12.5px] font-medium">
            {(exportMutation.error as Error).message}
          </p>
        )}
        {exportCap && (
          <p className="text-ink-400 mt-space-2 text-[11.5px]">
            Exports are capped at {exportCap.toLocaleString()} rows per range. Narrow the date range
            if you need more.
          </p>
        )}

        <div className="mt-space-4 border-line pt-space-3 border-t">
          <p className="text-ink-700 text-[12.5px] font-bold">Previously exported ranges</p>
          <div className="mt-space-2 max-h-56 space-y-1.5 overflow-y-auto">
            {history.isLoading ? (
              <p className="text-ink-400 text-[12.5px]">Loading…</p>
            ) : !history.data?.rows.length ? (
              <p className="text-ink-400 text-[12.5px]">No exports yet.</p>
            ) : (
              history.data.rows.map((r) => (
                <div
                  key={r.id}
                  className="bg-paper border-line gap-space-3 flex items-center justify-between rounded-lg border px-3 py-2 text-[12px]"
                >
                  <div className="min-w-0">
                    <p className="text-ink-700 truncate font-semibold">
                      {r.start_date ?? "—"} &rarr; {r.end_date ?? "—"}
                    </p>
                    <p className="text-ink-400 truncate">
                      {r.exported_by_label} · {r.created_at} · {r.row_count} rows
                      {r.truncated ? " (capped)" : ""}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
          {total > HISTORY_PAGE_SIZE && (
            <div className="gap-space-2 mt-space-2 flex items-center justify-end">
              <Button
                type="button"
                variant="ghost"
                size="md"
                className="h-8 px-2"
                disabled={historyPage <= 1}
                onClick={() => onHistoryPageChange(historyPage - 1)}
              >
                <ChevronLeft size={14} />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="md"
                className="h-8 px-2"
                disabled={!hasMore}
                onClick={() => onHistoryPageChange(historyPage + 1)}
              >
                <ChevronRight size={14} />
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
