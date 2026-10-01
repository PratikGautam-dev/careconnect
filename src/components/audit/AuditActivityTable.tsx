"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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
import { formatAuditDateTime } from "@/lib/formatDate";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

export type AuditEntry = {
  id: number;
  created_at: string;
  action: string;
  actor_label: string;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  actor_level: string;
  hospital_name: string | null;
  hospital_id: number | null;
};

type AuditActivityTableProps = {
  entries: AuditEntry[];
  isLoading?: boolean;
  title: string;
  subtitle?: string;
  emptyMessage?: string;
  showActorLevelFilter?: boolean;
  showHospitalColumn?: boolean;
  hospitalOptions?: { id: number; name: string }[] | null;
  pageSize?: number;
  onPageSizeChange?: (n: number) => void;
  pageNumber?: number;
  hasPrev?: boolean;
  hasNext?: boolean;
  goPrev?: () => void;
  goNext?: () => void;
  /** Filter state for URL/state sync */
  filters?: {
    search?: string;
    action?: string;
    entity_type?: string;
    date_from?: string;
    date_to?: string;
    actor_level?: string;
    hospital_id?: string;
  };
  onFiltersChange?: (next: Partial<AuditActivityTableProps["filters"]>) => void;
};

const ACTOR_LEVEL_OPTIONS = [
  { value: "platform_admin", label: "Platform" },
  { value: "portal", label: "Portal" },
];

const EMPTY_FILTERS = {
  search: "",
  action: "",
  entity_type: "",
  date_from: "",
  date_to: "",
  actor_level: "",
  hospital_id: "",
};

function hasActiveFilters(filters: AuditActivityTableProps["filters"]): boolean {
  if (!filters) return false;
  return Object.entries(filters).some(
    ([k, v]) => v && v !== EMPTY_FILTERS[k as keyof typeof EMPTY_FILTERS],
  );
}

export function AuditActivityTable({
  entries,
  isLoading = false,
  title,
  subtitle,
  emptyMessage = "No activity recorded yet.",
  showActorLevelFilter = false,
  showHospitalColumn = false,
  hospitalOptions = null,
  pageSize = 25,
  onPageSizeChange,
  pageNumber = 1,
  hasPrev = false,
  hasNext = false,
  goPrev,
  goNext,
  filters = EMPTY_FILTERS,
  onFiltersChange,
}: AuditActivityTableProps) {
  function setFilter<K extends keyof typeof EMPTY_FILTERS>(key: K, value: string) {
    onFiltersChange?.({ ...filters, [key]: value } as typeof filters);
  }

  const filteredEntries = entries.filter((entry) => {
    if (filters?.search) {
      const q = filters.search.toLowerCase();
      const haystack = [
        entry.action,
        entry.actor_label,
        entry.entity_type ?? "",
        entry.entity_id ? String(entry.entity_id) : "",
        entry.hospital_name ?? "",
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (filters?.action && entry.action !== filters.action) return false;
    if (filters?.entity_type && entry.entity_type !== filters.entity_type) return false;
    if (filters?.actor_level && entry.actor_level !== filters.actor_level) return false;
    if (filters?.hospital_id && String(entry.hospital_id ?? "") !== filters.hospital_id)
      return false;
    if (filters?.date_from) {
      const entryDate = new Date(entry.created_at).toISOString().slice(0, 10);
      if (entryDate < filters.date_from) return false;
    }
    if (filters?.date_to) {
      const entryDate = new Date(entry.created_at).toISOString().slice(0, 10);
      if (entryDate > filters.date_to) return false;
    }
    return true;
  });

  return (
    <Card className="p-space-4 mt-4">
      <div className="mb-space-3 gap-space-3 flex items-start justify-between">
        <div>
          <h3 className="text-label text-ink-900 font-bold">{title}</h3>
          {subtitle && <p className="text-hint mt-space-0.5">{subtitle}</p>}
        </div>
      </div>

      <div className="gap-space-2 mb-space-4 flex flex-wrap items-center">
        <div className="relative min-w-50 flex-1">
          <Search size={14} className="text-ink-400 absolute top-1/2 left-3 -translate-y-1/2" />
          <Input
            value={filters?.search ?? ""}
            onChange={(e) => setFilter("search", e.target.value)}
            placeholder="Search actor, action, or entity id…"
            className="h-9 pl-9 text-[12.5px]"
          />
        </div>
        <Input
          value={filters?.action ?? ""}
          onChange={(e) => setFilter("action", e.target.value)}
          placeholder="Action (e.g. hospital_subscription.assigned)"
          className="h-9 w-50 text-[12.5px]"
        />
        <Input
          value={filters?.entity_type ?? ""}
          onChange={(e) => setFilter("entity_type", e.target.value)}
          placeholder="Entity type"
          className="h-9 w-37.5 text-[12.5px]"
        />
        <Input
          type="date"
          value={filters?.date_from ?? ""}
          onChange={(e) => setFilter("date_from", e.target.value)}
          aria-label="From date"
          className="h-9 w-37.5 text-[12.5px]"
        />
        <Input
          type="date"
          value={filters?.date_to ?? ""}
          onChange={(e) => setFilter("date_to", e.target.value)}
          aria-label="To date"
          className="h-9 w-37.5 text-[12.5px]"
        />
        {showActorLevelFilter && (
          <FilterSelect
            value={filters?.actor_level ?? "all"}
            onChange={(v) => setFilter("actor_level", v === "all" ? "" : v)}
            options={ACTOR_LEVEL_OPTIONS}
            allLabel="All levels"
          />
        )}
        {showHospitalColumn && (
          <FilterSelect
            value={filters?.hospital_id ?? "all"}
            onChange={(v) => setFilter("hospital_id", v === "all" ? "" : v)}
            options={(hospitalOptions ?? []).map((h) => ({ value: String(h.id), label: h.name }))}
            allLabel="All tenants"
          />
        )}
        {hasActiveFilters(filters) && (
          <Button
            variant="secondary"
            className="h-9 text-[12.5px]"
            onClick={() => onFiltersChange?.(EMPTY_FILTERS)}
          >
            Clear filters
          </Button>
        )}
      </div>

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
          ) : filteredEntries.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-ink-400 py-space-6 text-center text-[13px]">
                {hasActiveFilters(filters) ? "No activity matches these filters." : emptyMessage}
              </TableCell>
            </TableRow>
          ) : (
            filteredEntries.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell className="text-ink-400 align-top whitespace-nowrap tabular-nums">
                  {formatAuditDateTime(entry.created_at)}
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
                    {entry.hospital_name ||
                      (entry.hospital_id ? `Tenant #${entry.hospital_id}` : "—")}
                  </TableCell>
                )}
                <TableCell className="text-ink-600 align-top whitespace-nowrap">
                  {entry.actor_label}
                </TableCell>
                <TableCell className="text-ink-600 align-top whitespace-nowrap">
                  {entry.entity_type
                    ? `${entry.entity_type}${entry.entity_id ? ` #${entry.entity_id}` : ""}`
                    : "—"}
                </TableCell>
                <TableCell className="align-top">
                  <AuditChangeDiff entry={entry} />
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {(hasPrev || hasNext || onPageSizeChange) && (
        <div className="mt-space-4 gap-space-3 flex flex-wrap items-center justify-between">
          <div className="gap-space-2 flex items-center">
            <span className="text-ink-400 text-[12.5px]">Rows per page</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange?.(Number(e.target.value))}
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
            <Button
              variant="secondary"
              className="px-space-3 h-9"
              disabled={!hasPrev}
              onClick={goPrev}
            >
              <ChevronLeft size={14} /> Previous
            </Button>
            <Button
              variant="secondary"
              className="px-space-3 h-9"
              disabled={!hasNext}
              onClick={goNext}
            >
              Next <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
