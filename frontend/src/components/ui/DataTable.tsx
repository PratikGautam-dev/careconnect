"use client";
"use no memo";

import { Fragment } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Button } from "@/components/ui/Button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/cn";

type DataTableProps<TData> = {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];
  /** Stable row id (defaults to row index) -- pass this whenever `data` has
   * its own id, so client-side pagination/selection survive a row's position
   * shifting between renders (e.g. after a filter changes). */
  getRowId?: (row: TData, index: number) => string;
  /** Rows per page for the built-in client-side pagination (TanStack's
   * getPaginationRowModel) -- this table always paginates client-side today,
   * since every /api/portal/* list route this feeds still returns its whole
   * hospital-scoped result set in one shot. */
  pageSize?: number;
  /** Renders an extra full-width row directly under a data row when it
   * returns true for that row -- this table's one hook for the inline
   * reschedule/cancel/follow-up panels several portal pages already show
   * per-row, so that bespoke business logic stays page-owned rather than
   * something this generic component has to understand. */
  isRowExpanded?: (row: TData) => boolean;
  renderRowDetail?: (row: TData) => React.ReactNode;
  rowClassName?: (row: TData) => string;
  /** Makes the whole row clickable (e.g. navigate to a detail page) --
   * individual cells (a checkbox, a delete button) still need their own
   * onClick(e) => e.stopPropagation() to opt out, same as this app's
   * hand-rolled tables already did. */
  onRowClick?: (row: TData) => void;
  emptyMessage?: string;
  /** Extra classes on the scroll container around <Table> -- e.g. a fixed
   * max-height for a small preview list (DoctorCsvImport's CSV row
   * preview), which needs its own vertical scroll independent of the page. */
  containerClassName?: string;
  /** Pins the header row to the top of containerClassName's own scroll
   * container (only useful together with a max-height containerClassName --
   * a page-level table has nothing shorter than the viewport to stick to). */
  stickyHeader?: boolean;
};

/** Shared, reusable table for portal list pages -- headless via
 * @tanstack/react-table (same library sarvaya-dashboard's own DataTable
 * uses), styled with this app's own Tailwind tokens rather than a component
 * library. Always renders as a single wide table with a horizontal scroll
 * container (no separate mobile card layout -- confirmed with the user:
 * that's the wanted responsive behavior here, matching sarvaya-dashboard's
 * own table). Selection/permission-gating/row actions all stay as ordinary
 * column cells the caller defines -- this component only owns rendering +
 * client-side pagination + the optional expanded-row slot above. */
export function DataTable<TData>({
  columns,
  data,
  getRowId,
  pageSize = 25,
  isRowExpanded,
  renderRowDetail,
  rowClassName,
  onRowClick,
  emptyMessage = "No results.",
  containerClassName,
  stickyHeader = false,
}: DataTableProps<TData>) {
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table can't be safely memoized (file opts out via "use no memo")
  const table = useReactTable({
    data,
    columns,
    getRowId: getRowId as ((row: TData, index: number) => string) | undefined,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  });

  const rows = table.getRowModel().rows;
  const { pageIndex, pageSize: currentPageSize } = table.getState().pagination;
  const totalRows = table.getFilteredRowModel().rows.length;

  return (
    <div>
      <Table containerClassName={containerClassName}>
        <TableHeader className={cn(stickyHeader && "sticky top-0 z-10 bg-card")}>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        {rows.length === 0 ? (
          <TableBody>
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={columns.length} className="py-space-4 text-center text-ink-400">
                {emptyMessage}
              </TableCell>
            </TableRow>
          </TableBody>
        ) : (
          <TableBody>
            {rows.map((row) => {
              const expanded = isRowExpanded?.(row.original) ?? false;
              return (
                <Fragment key={row.id}>
                  <TableRow
                    className={cn(onRowClick && "cursor-pointer", expanded && "border-b-0", rowClassName?.(row.original))}
                    onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                    ))}
                  </TableRow>
                  {expanded && renderRowDetail && (
                    <TableRow>
                      <TableCell colSpan={row.getVisibleCells().length} className="pb-space-3">
                        {renderRowDetail(row.original)}
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
          </TableBody>
        )}
      </Table>

      {totalRows > currentPageSize && (
        <div className="mt-space-3 flex flex-col items-center justify-between gap-space-2 border-t border-line pt-space-3 sm:flex-row">
          <p className="text-[12px] text-ink-400">
            Showing {pageIndex * currentPageSize + 1}–{Math.min((pageIndex + 1) * currentPageSize, totalRows)} of {totalRows}
          </p>
          <div className="flex items-center gap-space-2">
            <Button
              size="md"
              variant="secondary"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ArrowLeft size={13} /> Prev
            </Button>
            <span className="text-[12px] font-semibold text-ink-600">
              Page {pageIndex + 1} of {Math.max(1, table.getPageCount())}
            </span>
            <Button size="md" variant="secondary" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
              Next <ArrowRight size={13} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
