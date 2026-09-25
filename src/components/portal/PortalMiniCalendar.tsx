"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { formatDateHeading, formatMonthYear, formatTimeOnly } from "@/lib/formatDate";
import {
  usePortalBookingsCalendar,
  type CalendarAppointment,
} from "@/hooks/usePortalBookingsCalendar";

type Appointment = CalendarAppointment;

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};
const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed",
  cancelled: "Cancelled",
  rescheduled: "Rescheduled",
  attended: "Attended",
  no_show: "No-show",
};

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function dateKey(y: number, m: number, d: number) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

type Props = {
  /** Scopes which appointments count toward a day's dot -- "doctor" for the
   * Doctor appointments page, "diagnostic" for Diagnostic & lab, "daycare"
   * for Daycare appointments, omitted (all types) for the Dashboard. Mirrors
   * useAppointments' own AppointmentCategory / the backend's
   * _apply_category_filter split. */
  category?: "doctor" | "diagnostic" | "daycare";
};

/** Real month-of-bookings calendar -- one fetch per month navigated to (not
 * per day, not on every render), grouped into day cells client-side; click a
 * day with bookings to see that day's list below the grid. Same fetch-by-
 * month + group-by-day + click-to-reveal pattern the doctor portal's own
 * AppointmentCalendar (frontend/src/components/doctor/AppointmentCalendar.tsx)
 * already established for a single doctor's appointments -- this is that
 * same pattern, hospital-wide and category-scoped, backed by
 * GET /api/portal/bookings/calendar (60s-cached server-side, see that
 * route's own comment on why no invalidation is wired up for it). */
export function PortalMiniCalendar({ category }: Props) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1); // 1-12
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const { appointments, error } = usePortalBookingsCalendar(year, month, category);

  // Resets the selected-day drill-down whenever the month being viewed
  // changes -- adjusted directly in the render body (comparing against a
  // tracked previous [year, month], per React's own "Adjusting some state
  // when a prop changes" guide) rather than in an effect, since this isn't
  // synchronizing with anything external, just resetting local UI state.
  const [prevYearMonth, setPrevYearMonth] = useState(`${year}-${month}`);
  const yearMonth = `${year}-${month}`;
  if (yearMonth !== prevYearMonth) {
    setPrevYearMonth(yearMonth);
    setSelectedDay(null);
  }

  function goToMonth(delta: number) {
    let m = month + delta;
    let y = year;
    if (m > 12) {
      m = 1;
      y += 1;
    }
    if (m < 1) {
      m = 12;
      y -= 1;
    }
    setMonth(m);
    setYear(y);
  }

  function goToToday() {
    setYear(now.getFullYear());
    setMonth(now.getMonth() + 1);
  }

  const byDay = new Map<string, Appointment[]>();
  for (const a of appointments || []) {
    const d = new Date(a.scheduled_at);
    const key = dateKey(d.getFullYear(), d.getMonth() + 1, d.getDate());
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(a);
  }

  const firstOfMonth = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const leadingBlanks = firstOfMonth.getDay();
  const todayKey = dateKey(now.getFullYear(), now.getMonth() + 1, now.getDate());
  const monthLabel = formatMonthYear(firstOfMonth);

  const cells: { key: string | null; day: number | null }[] = [];
  for (let i = 0; i < leadingBlanks; i++) cells.push({ key: null, day: null });
  for (let d = 1; d <= daysInMonth; d++) cells.push({ key: dateKey(year, month, d), day: d });

  const selectedAppointments = selectedDay ? byDay.get(selectedDay) || [] : [];

  return (
    <Card className="p-space-4">
      <div className="mb-space-4 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">{monthLabel}</h3>
        <div className="gap-space-1 flex items-center">
          <button
            type="button"
            onClick={() => goToMonth(-1)}
            aria-label="Previous month"
            className="text-ink-600 flex h-7 w-7 items-center justify-center rounded-md transition-colors duration-150 hover:bg-black/4"
          >
            <ChevronLeft size={15} />
          </button>
          <button
            type="button"
            onClick={goToToday}
            className="px-space-2 text-ink-600 rounded-md py-1 text-[11.5px] font-semibold transition-colors duration-150 hover:bg-black/4"
          >
            Today
          </button>
          <button
            type="button"
            onClick={() => goToMonth(1)}
            aria-label="Next month"
            className="text-ink-600 flex h-7 w-7 items-center justify-center rounded-md transition-colors duration-150 hover:bg-black/4"
          >
            <ChevronRight size={15} />
          </button>
        </div>
      </div>

      {error && <p className="mb-space-3 text-error text-[12.5px]">{error}</p>}

      <div className="text-ink-400 grid grid-cols-7 gap-1 text-center text-[10.5px] font-semibold">
        {WEEKDAY_LABELS.map((w) => (
          <div key={w} className="py-1">
            {w}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {cells.map((c, i) => {
          if (c.day === null) return <div key={`b${i}`} />;
          const count = byDay.get(c.key!)?.length || 0;
          const isToday = c.key === todayKey;
          const isSelected = c.key === selectedDay;
          return (
            <button
              key={c.key}
              type="button"
              disabled={count === 0}
              onClick={() => setSelectedDay(isSelected ? null : c.key)}
              className={cn(
                "flex aspect-square flex-col items-center justify-center gap-0.5 rounded-md border text-[12px] transition-colors duration-150",
                isSelected
                  ? "border-brand-600 bg-brand-600 text-white"
                  : isToday
                    ? "border-brand-300 bg-brand-50 text-ink-900"
                    : count > 0
                      ? "border-line bg-card text-ink-900 hover:border-brand-300 cursor-pointer"
                      : "text-ink-300 border-transparent",
              )}
            >
              <span className={cn("font-semibold", isSelected && "text-white")}>{c.day}</span>
              {count > 0 && (
                <span
                  className={cn(
                    "flex h-3.5 min-w-3.5 items-center justify-center rounded-full px-1 text-[9px] font-bold tabular-nums",
                    isSelected ? "bg-white/25 text-white" : "bg-brand-600 text-white",
                  )}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {selectedDay && (
        <div className="mt-space-4 space-y-space-2 border-line pt-space-3 border-t">
          <p className="text-ink-400 text-[11.5px] font-semibold">
            {selectedAppointments.length} appointment{selectedAppointments.length === 1 ? "" : "s"}{" "}
            on {formatDateHeading(selectedDay)}
          </p>
          {selectedAppointments
            .slice()
            .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at))
            .map((a) => (
              <div
                key={a.id}
                className="gap-space-3 bg-paper p-space-2.5 flex items-center rounded-md"
              >
                <span className="text-ink-900 w-16 shrink-0 text-[12px] font-semibold tabular-nums">
                  {formatTimeOnly(a.scheduled_at)}
                </span>
                <span className="text-ink-600 min-w-0 flex-1 truncate text-[12px]">
                  {a.patient_name || a.patient_display_id || a.phone}
                </span>
                <span
                  className={cn(
                    "px-space-2 shrink-0 rounded-full py-0.5 text-[10px] font-semibold",
                    STATUS_STYLES[a.status] || "text-ink-600 bg-black/4",
                  )}
                >
                  {STATUS_LABELS[a.status] || a.status}
                </span>
              </div>
            ))}
        </div>
      )}
    </Card>
  );
}
