"use client";

import { useEffect, useRef, useState } from "react";
import { CalendarRange } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

const MONTHS_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** "1 Sep 2026" for a plain YYYY-MM-DD string, parsed at local midnight --
 * same manual-format reasoning as lib/formatDate.ts's own formatters (avoids
 * a server/client locale hydration mismatch). */
function formatRangeDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  return `${d} ${MONTHS_SHORT[m - 1]} ${y}`;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

type Props = {
  dateFrom: string;
  dateTo: string;
  onChange: (dateFrom: string, dateTo: string) => void;
  className?: string;
};

/** Shared date-range control -- a button showing the formatted range that
 * opens a dropdown with two native date inputs, a one-click "Today" preset,
 * and Apply, closed on outside click. Originally built just for the Report
 * Analytics page (as ReportDateRangePicker); promoted here once the admin
 * Appointment Billing page needed the exact same control instead of its own
 * hand-rolled pair of `<input type="date">` + a separate "Today" link --
 * same "native input, app-styled wrapper" approach Input.tsx/FilterSelect.tsx
 * already use everywhere else rather than a bespoke calendar-grid widget. */
export function DateRangePicker({ dateFrom, dateTo, onChange, className }: Props) {
  const [open, setOpen] = useState(false);
  const [draftFrom, setDraftFrom] = useState(dateFrom);
  const [draftTo, setDraftTo] = useState(dateTo);
  const containerRef = useRef<HTMLDivElement>(null);

  // Draft state only needs to pick up the latest dateFrom/dateTo at the
  // moment the popover opens (so it starts from the applied range, not
  // whatever was last typed and abandoned) -- doing that here, in the same
  // handler that flips `open`, avoids an effect whose only job would be
  // mirroring props into state on every parent re-render.
  function handleToggleOpen() {
    setOpen((v) => {
      const next = !v;
      if (next) {
        setDraftFrom(dateFrom);
        setDraftTo(dateTo);
      }
      return next;
    });
  }

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function handleApply() {
    if (draftFrom && draftTo && draftFrom <= draftTo) {
      onChange(draftFrom, draftTo);
      setOpen(false);
    }
  }

  function handleToday() {
    const today = todayStr();
    onChange(today, today);
    setOpen(false);
  }

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={handleToggleOpen}
        className="border-line bg-card gap-space-2 px-space-3 text-ink-900 hover:border-brand-300 flex h-10 items-center rounded-md border text-[13px] font-medium shadow-[var(--shadow-sm)] transition-colors duration-150"
      >
        <CalendarRange size={15} className="text-ink-400" />
        {formatRangeDate(dateFrom)} – {formatRangeDate(dateTo)}
      </button>

      {open && (
        <div className="border-line bg-card p-space-4 gap-space-3 mt-space-1 absolute top-full right-0 z-20 flex w-72 flex-col rounded-md border shadow-[var(--shadow-md)]">
          <button
            type="button"
            onClick={handleToday}
            className="text-brand-600 self-start text-[12.5px] font-semibold hover:underline"
          >
            Today
          </button>
          <div>
            <label className="text-hint mb-space-1 block">From</label>
            <Input
              type="date"
              value={draftFrom}
              max={draftTo || undefined}
              onChange={(e) => setDraftFrom(e.target.value)}
              className="h-9"
            />
          </div>
          <div>
            <label className="text-hint mb-space-1 block">To</label>
            <Input
              type="date"
              value={draftTo}
              min={draftFrom || undefined}
              onChange={(e) => setDraftTo(e.target.value)}
              className="h-9"
            />
          </div>
          <Button
            type="button"
            size="md"
            onClick={handleApply}
            disabled={!draftFrom || !draftTo || draftFrom > draftTo}
            className="w-full"
          >
            Apply
          </Button>
        </div>
      )}
    </div>
  );
}
