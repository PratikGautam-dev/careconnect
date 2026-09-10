"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { formatMonthYear } from "@/lib/formatDate";

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function buildMonthGrid(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

// Real, date-correct month grid, but no events plotted -- no calendar/
// scheduling backend exists (PortalSidebar dropped its own "Calendar" nav
// item for the same reason). Shared across portal pages (dashboard,
// appointments, ...) -- purely a date widget, nothing page-specific.
export function PortalMiniCalendar() {
  const today = new Date();
  const [cursor, setCursor] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));

  const grid = buildMonthGrid(cursor.getFullYear(), cursor.getMonth());
  const monthLabel = formatMonthYear(cursor);
  const isCurrentMonth = cursor.getFullYear() === today.getFullYear() && cursor.getMonth() === today.getMonth();

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">{monthLabel}</h3>
        <div className="flex items-center gap-space-1">
          <button
            type="button"
            aria-label="Previous month"
            onClick={() => setCursor((c) => new Date(c.getFullYear(), c.getMonth() - 1, 1))}
            className="flex h-6 w-6 items-center justify-center rounded text-ink-400 hover:bg-paper hover:text-ink-900"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            aria-label="Next month"
            onClick={() => setCursor((c) => new Date(c.getFullYear(), c.getMonth() + 1, 1))}
            className="flex h-6 w-6 items-center justify-center rounded text-ink-400 hover:bg-paper hover:text-ink-900"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-y-space-1 text-center text-[11px]">
        {WEEKDAY_LABELS.map((w) => (
          <span key={w} className="font-semibold text-ink-400">
            {w}
          </span>
        ))}
        {grid.map((day, i) => {
          const isToday = isCurrentMonth && day === today.getDate();
          return (
            <span
              key={i}
              className={cn(
                "mx-auto flex h-6 w-6 items-center justify-center rounded-full text-[12px]",
                day === null && "invisible",
                isToday ? "bg-brand-600 font-semibold text-white" : "text-ink-900",
              )}
            >
              {day}
            </span>
          );
        })}
      </div>
      <p className="text-hint mt-space-3">No scheduling data source yet — dates only.</p>
    </Card>
  );
}
