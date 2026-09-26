"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";

const PAGE_SIZE_OPTIONS = [25, 50, 100];

type Props = {
  pageNumber: number;
  hasNext: boolean;
  hasPrev: boolean;
  goNext: () => void;
  goPrev: () => void;
  pageSize: number;
  onPageSizeChange: (n: number) => void;
};

/** Next/Previous + rows-per-page footer for a keyset-paginated (before_id/
 * next_cursor/has_more) list -- shared by Doctors/Staff/Patients, which all
 * page via useDoctors()/useStaff()/usePatients() -> useCursorPage.ts. No
 * numbered "jump to page N" (cursor pagination structurally can't do that
 * -- see the Audit Log design discussion this mirrors) and no `DataTable`
 * built-in pager either (that one needs an exact filtered total to compute
 * page count, which these lists deliberately don't fetch -- same
 * "constant-cost paging over an OFFSET scan" tradeoff audit logs made). */
export function CursorPaginationControls({
  pageNumber,
  hasNext,
  hasPrev,
  goNext,
  goPrev,
  pageSize,
  onPageSizeChange,
}: Props) {
  return (
    <div className="mt-space-3 gap-space-2 border-line pt-space-3 flex flex-col items-center justify-between border-t sm:flex-row">
      <div className="gap-space-2 flex items-center">
        <span className="text-ink-400 text-[12px]">Rows per page</span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="border-line bg-card px-space-2 text-ink-900 h-8 rounded-md border text-[12px]"
          aria-label="Rows per page"
        >
          {PAGE_SIZE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n} per page
            </option>
          ))}
        </select>
      </div>
      <div className="gap-space-2 flex items-center">
        <Button size="md" variant="secondary" onClick={goPrev} disabled={!hasPrev}>
          <ChevronLeft size={13} /> Prev
        </Button>
        <span className="text-ink-600 text-[12px] font-semibold">Page {pageNumber}</span>
        <Button size="md" variant="secondary" onClick={goNext} disabled={!hasNext}>
          Next <ChevronRight size={13} />
        </Button>
      </div>
    </div>
  );
}
