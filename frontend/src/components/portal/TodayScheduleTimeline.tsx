"use client";

import { CalendarCheck, type LucideIcon } from "lucide-react";
import { TYPE_ICONS } from "@/app/portal/appointments/_components/appointments-columns";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import { cn } from "@/lib/cn";

type TimelineAppointment = {
  id: number;
  scheduled_at: string;
  department_name: string;
  appointment_type_id: string | null;
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** Shared vertical timeline of a doctor's own appointments for one day --
 * used by both the Dashboard's "Today's schedule" card and the Schedule
 * page's own "Today's schedule" panel. Built from real appointments only
 * (no fabricated lunch-break/on-call blocks -- neither has a data source
 * anywhere in this app). */
export function TodayScheduleTimeline({ appointments }: { appointments: TimelineAppointment[] }) {
  if (appointments.length === 0) {
    return <p className="py-space-4 text-center text-[13px] text-ink-400">Nothing scheduled for today.</p>;
  }
  return (
    <ol>
      {appointments.map((a, i) => {
        const TypeIcon: LucideIcon = (a.appointment_type_id && TYPE_ICONS[a.appointment_type_id]) || CalendarCheck;
        return (
          <li key={a.id} className="flex gap-space-3">
            <div className="flex flex-col items-center">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                <TypeIcon size={13} />
              </span>
              {i < appointments.length - 1 && <span className="w-px flex-1 bg-line" />}
            </div>
            <div className={cn("min-w-0", i < appointments.length - 1 ? "pb-space-4" : "pb-space-1")}>
              <p className="text-[11.5px] font-semibold text-ink-400">{formatTime(a.scheduled_at)}</p>
              <p className="truncate text-[13px] font-semibold text-ink-900">
                {(a.appointment_type_id && TYPE_LABELS[a.appointment_type_id]) || "Consultation"}
              </p>
              <p className="truncate text-[12px] text-ink-600">{a.department_name}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
