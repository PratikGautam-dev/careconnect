"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { downloadBlob } from "@/lib/downloadBlob";
import { toast } from "@/lib/toast";

export type ExportHistoryEntry = {
  id: number;
  module: string;
  start_date: string | null;
  end_date: string | null;
  row_count: number;
  truncated: boolean;
  file_name: string;
  exported_by_label: string;
  created_at: string;
};

export type ExportHistoryResponse = {
  total: number;
  rows: ExportHistoryEntry[];
};

type FetchBlobResult =
  | { ok: true; blob: Blob; headers: Record<string, string> }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

type FetchJsonResult =
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

export type FetchBlobFn = (path: string) => Promise<FetchBlobResult>;
export type FetchJsonFn = (path: string) => Promise<FetchJsonResult>;

export type ExportParams = { dateFrom?: string; dateTo?: string } & Record<
  string,
  string | undefined
>;

function buildQueryString(params: ExportParams): string {
  const { dateFrom, dateTo, ...rest } = params;
  const entries = Object.entries({ date_from: dateFrom, date_to: dateTo, ...rest }).filter(
    ([, v]) => v !== undefined && v !== "",
  ) as [string, string][];
  return new URLSearchParams(entries).toString();
}

/** CSV-export mutation shared by every ExportDialog instance -- pass in
 * whichever fetchBlob fits the page's own auth context (adminFetchBlob for
 * admin pages, staffFetchBlob/portalFetchBlob for portal pages); this hook
 * has no opinion on which one, so it works under either. Downloads the
 * file via downloadBlob() on success and toasts a warning if the backend's
 * x-truncated header says the row cap was hit. */
export function useCsvExport(fetchBlob: FetchBlobFn, exportUrl: string, fallbackFilename: string) {
  return useMutation({
    mutationFn: async (params: ExportParams) => {
      const qs = buildQueryString(params);
      const result = await fetchBlob(`${exportUrl}${qs ? `?${qs}` : ""}`);
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
      downloadBlob(result.blob, fallbackFilename, result.headers["content-disposition"]);
      if (result.headers["x-truncated"] === "true") {
        toast.warning(
          "Export limited",
          "Only the first rows were exported — narrow your date range for the full set.",
        );
      }
      return result;
    },
  });
}

/** Paginated export-history list shared by every ExportDialog instance --
 * same fetchJson-parameter abstraction as useCsvExport above. */
export function useExportHistory(
  fetchJson: FetchJsonFn,
  historyUrl: string,
  module: string,
  page: number,
  limit = 10,
  enabled = true,
) {
  return useQuery({
    queryKey: ["export-history", historyUrl, module, page, limit],
    enabled,
    queryFn: async () => {
      const qs = new URLSearchParams({
        module,
        page: String(page),
        limit: String(limit),
      }).toString();
      const result = await fetchJson(`${historyUrl}?${qs}`);
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
      return result.data as ExportHistoryResponse;
    },
  });
}
