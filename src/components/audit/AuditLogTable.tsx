"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { FilterSelect } from "@/components/ui/FilterSelect";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/cn";
import { AuditChangeDiff } from "@/components/audit/AuditChangeDiff";
import { AuditLogFilters, EMPTY_AUDIT_LOG_FILTERS, useAuditLogPage } from "@/hooks/useAuditLogPage";

const PAGE_SIZE_OPTIONS = [25, 50, 100];

const ACTOR_LEVEL_OPTIONS = [
  { value: "platform_admin", label: "Platform" },
  { value: "portal", label: "Portal" },
];

type HospitalOption = { id: number; name: string };

type AuditLogTableProps = {
  page: ReturnType<typeof useAuditLogPage>;
  filters: AuditLogFilters;
  onFiltersChange: (next: AuditLogFilters) => void;
  pageSize: number;
  onPageSizeChange: (n: number) => void;
  /** Admin-only: cross-tenant view shows which hospital each row belongs
   * to, and lets you narrow to one. Omitted entirely on the portal page
   * (single-tenant by construction, nothing to show/filter). */
  showHospitalColumn?: boolean;
  hospitalOptions?: HospitalOption[] | null;
  /** Admin-only: platform vs portal actor level. The portal page never
   * shows this -- its route hardcodes actor_level="portal" server-side
   * regardless of what the frontend sends, so a filter here would be
   * decorative at best. */
  showActorLevelFilter?: boolean;
};

/** Shared table + filter bar + cursor pager for both audit-log pages
 * (admin's cross-tenant /admin/audit-log and the portal's own /portal/
 * settings/activity). Visual shape is identical between them; only the
 * available filters and columns differ, both driven by the two boolean
 * props above rather than two near-duplicate components. */
export function AuditLogTable({
  page,
  filters,
  onFiltersChange,
  pageSize,
  onPageSizeChange,
  showHospitalColumn,
  hospitalOptions,
  showActorLevelFilter,
}: AuditLogTableProps) {
  const { entries, isLoading, error, hasNext, hasPrev, pageNumber, goNext, goPrev } = page;

  function set<K extends keyof AuditLogFilters>(key: K, value: AuditLogFilters[K]) {
    onFiltersChange({ ...filters, [key]: value });
  }

  const hasActiveFilters = Object.entries(filters).some(
    ([k, v]) => v !== EMPTY_AUDIT_LOG_FILTERS[k as keyof AuditLogFilters],
  );

  return (
    <div>
      <div className="gap-space-2 mb-space-4 flex flex-wrap items-center">
        <div className="relative min-w-50 flex-1">
          <Search size={14} className="text-ink-400 absolute top-1/2 left-3 -translate-y-1/2" />
          <Input
            value={filters.search}
            onChange={(e) => set("search", e.target.value)}
            placeholder="Search actor, action, or entity id…"
            className="h-9 pl-9 text-[12.5px]"
          />
        </div>
        <Input
          value={filters.action}
          onChange={(e) => set("action", e.target.value)}
          placeholder="Action (e.g. doctor.create)"
          className="h-9 w-50 text-[12.5px]"
        />
        <Input
          value={filters.entity_type}
          onChange={(e) => set("entity_type", e.target.value)}
          placeholder="Entity type"
          className="h-9 w-37.5 text-[12.5px]"
        />
        <Input
          type="date"
          value={filters.date_from}
          onChange={(e) => set("date_from", e.target.value)}
          aria-label="From date"
          className="h-9 w-37.5 text-[12.5px]"
        />
        <Input
          type="date"
          value={filters.date_to}
          onChange={(e) => set("date_to", e.target.value)}
          aria-label="To date"
          className="h-9 w-37.5 text-[12.5px]"
        />
        {showActorLevelFilter && (
          <FilterSelect
            value={filters.actor_level || "all"}
            onChange={(v) => set("actor_level", v === "all" ? "" : (v as AuditLogFilters["actor_level"]))}
            options={ACTOR_LEVEL_OPTIONS}
            allLabel="All levels"
          />
        )}
        {showHospitalColumn && (
          <FilterSelect
            value={filters.hospital_id || "all"}
            onChange={(v) => set("hospital_id", v === "all" ? "" : v)}
            options={(hospitalOptions ?? []).map((h) => ({ value: String(h.id), label: h.name }))}
            allLabel="All tenants"
          />
        )}
        {hasActiveFilters && (
          <Button variant="secondary" className="h-9 text-[12.5px]" onClick={() => onFiltersChange(EMPTY_AUDIT_LOG_FILTERS)}>
            Clear filters
          </Button>
        )}
      </div>

      {error && <p className="mb-space-3 text-error text-[13px]">{error}</p>}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="whitespace-nowrap">Date</TableHead>
            <TableHead>Action</TableHead>
            {showActorLevelFilter && <TableHead>Level</TableHead>}
            {showHospitalColumn && <TableHead>Tenant</TableHead>}
            <TableHead>Actor</TableHead>
            <TableHead>Entity</TableHead>
            <TableHead>Changes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={7} className="text-ink-400 py-space-6 text-center text-[13px]">
                Loading…
              </TableCell>
            </TableRow>
          ) : entries.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-ink-400 py-space-6 text-center text-[13px]">
                {hasActiveFilters ? "No activity matches these filters." : "No activity recorded yet."}
              </TableCell>
            </TableRow>
          ) : (
            entries.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell className="text-ink-400 whitespace-nowrap align-top tabular-nums">
                  {entry.created_at}
                </TableCell>
                <TableCell className="text-ink-900 align-top font-medium whitespace-nowrap">
                  {entry.action}
                </TableCell>
                {showActorLevelFilter && (
                  <TableCell className="align-top">
                    <span
                      className={cn(
                        "px-space-2 rounded-full py-0.5 text-[11px] font-semibold whitespace-nowrap",
                        entry.actor_level === "platform_admin"
                          ? "bg-brand-50 text-brand-700"
                          : "text-ink-600 bg-black/5",
                      )}
                    >
                      {entry.actor_level === "platform_admin" ? "Platform" : "Portal"}
                    </span>
                  </TableCell>
                )}
                {showHospitalColumn && (
                  <TableCell className="text-ink-600 align-top whitespace-nowrap">
                    {entry.hospital_name || (entry.hospital_id ? `Tenant #${entry.hospital_id}` : "—")}
                  </TableCell>
                )}
                <TableCell className="text-ink-600 align-top whitespace-nowrap">{entry.actor_label}</TableCell>
                <TableCell className="text-ink-600 align-top whitespace-nowrap">
                  {entry.entity_type ? `${entry.entity_type}${entry.entity_id ? ` #${entry.entity_id}` : ""}` : "—"}
                </TableCell>
                <TableCell className="align-top">
                  <AuditChangeDiff entry={entry} />
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <div className="mt-space-4 gap-space-3 flex flex-wrap items-center justify-between">
        <div className="gap-space-2 flex items-center">
          <span className="text-ink-400 text-[12.5px]">Rows per page</span>
          {/* Plain select, not FilterSelect -- FilterSelect always injects an
              "All X" sentinel option, which doesn't fit a page-size picker
              (there's no unfiltered state for page size). */}
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="border-line bg-card px-space-2 text-ink-900 h-9 rounded-md border text-[12.5px]"
          >
            {PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <div className="gap-space-2 flex items-center">
          <span className="text-ink-400 text-[12.5px]">Page {pageNumber}</span>
          <Button variant="secondary" className="h-9 px-space-3" disabled={!hasPrev} onClick={goPrev}>
            <ChevronLeft size={14} /> Previous
          </Button>
          <Button variant="secondary" className="h-9 px-space-3" disabled={!hasNext} onClick={goNext}>
            Next <ChevronRight size={14} />
          </Button>
        </div>
      </div>
    </div>
  );
}
