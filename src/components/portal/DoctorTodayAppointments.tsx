"use client";

import { cn } from "@/lib/cn";
import { formatTimeOnly } from "@/lib/formatDate";
import { useDoctorTodayAppointments } from "@/hooks/useDoctorTodayAppointments";

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

export function DoctorTodayAppointments({ doctorId }: { doctorId: string }) {
  const { appointments } = useDoctorTodayAppointments(doctorId);

  return (
    <div className="border-line bg-paper p-space-3 rounded-lg border">
      <p className="text-label mb-space-2 text-ink-900 font-semibold">Today&apos;s appointments</p>
      {appointments === null ? (
        <p className="text-hint">Loading…</p>
      ) : appointments.length === 0 ? (
        <p className="text-hint">Nothing scheduled today.</p>
      ) : (
        <ul className="space-y-space-1">
          {appointments.map((a) => (
            <li key={a.id} className="bg-card px-space-3 py-space-2 rounded-md text-[12.5px]">
              <div className="flex items-center justify-between">
                <span className="text-ink-900 tabular-nums">{formatTimeOnly(a.scheduled_at)}</span>
                <span className="text-ink-600">{a.phone}</span>
                <span
                  className={cn(
                    "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                    STATUS_STYLES[a.status] || "text-ink-600 bg-black/[0.04]",
                  )}
                >
                  {STATUS_LABELS[a.status] || a.status}
                </span>
              </div>
              {/* Only shown for a tele-consultation row that has a video link. */}
              {a.appointment_type_id === "tele" && a.video_link && (
                <a
                  href={a.video_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-space-1 text-brand-600 inline-flex items-center gap-1 text-[12px] font-semibold hover:underline"
                >
                  🎥 Join video consultation
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
