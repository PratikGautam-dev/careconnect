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
 * a server/client locale hydration mismatch), kept local to this component
 * since no other page needs this exact "D Mon YYYY" shape yet. */
function formatRangeDate(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  return `${d} ${MONTHS_SHORT[m - 1]} ${y}`;
}

type Props = {
  dateFrom: string;
  dateTo: string;
  onChange: (dateFrom: string, dateTo: string) => void;
  className?: string;
};

/** No reusable date-range picker existed anywhere in the codebase (checked
 * for DateRange/react-day-picker/Popover -- every other page's date control
 * is either a single native `<input type="date">` (Attendance Overview) or
 * a from-scratch month calendar grid, PortalMiniCalendar). Built new, kept
 * deliberately small: a button showing the formatted range (matches the
 * reference screenshot's "1 Sep 2026 - 30 Sep 2026" button) that opens a
 * dropdown with two native date inputs + Apply, closed on outside click --
 * same "native input, app-styled wrapper" approach Input.tsx/FilterSelect.tsx
 * already use everywhere else rather than a bespoke calendar-grid widget. */
export function ReportDateRangePicker({ dateFrom, dateTo, onChange, className }: Props) {
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
