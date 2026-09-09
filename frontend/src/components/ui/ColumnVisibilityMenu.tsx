"use client";

import { useEffect, useRef, useState } from "react";
import { Columns3 } from "lucide-react";
import type { Table } from "@tanstack/react-table";
import { cn } from "@/lib/cn";

/** "Show/hide columns" trigger + popover for DataTable -- lists every column
 * that opted in (ColumnDef didn't set `enableHiding: false`), toggled via
 * TanStack's own column.getIsVisible()/toggleVisibility(). Column label
 * falls back to its id when `header` isn't a plain string (e.g. a checkbox
 * or icon-only header). */
export function ColumnVisibilityMenu<TData>({ table }: { table: Table<TData> }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const columns = table.getAllLeafColumns().filter((c) => c.getCanHide());
  if (columns.length === 0) return null;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-9 items-center gap-space-2 rounded-md border border-line bg-card px-space-3 text-[12.5px] font-semibold text-ink-700 shadow-[var(--shadow-sm)] hover:border-brand-300 hover:bg-brand-50"
      >
        <Columns3 size={14} /> Columns
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-space-1 w-56 rounded-md border border-line bg-card p-space-2 shadow-[var(--shadow-md)]">
          {columns.map((column) => {
            const header = column.columnDef.header;
            const label = typeof header === "string" && header ? header : column.id;
            return (
              <label
                key={column.id}
                className={cn(
                  "flex cursor-pointer items-center gap-space-2 rounded-md px-space-2 py-space-1.5 text-[13px] text-ink-900 hover:bg-paper",
                )}
              >
                <input
                  type="checkbox"
                  checked={column.getIsVisible()}
                  onChange={(e) => column.toggleVisibility(e.target.checked)}
                  className="h-3.5 w-3.5 accent-brand-600"
                />
                <span>{label}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
