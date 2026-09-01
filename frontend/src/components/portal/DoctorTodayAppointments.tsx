"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { formatTimeOnly } from "@/lib/formatDate";
import { portalFetch } from "@/lib/portalAuth";

type Appointment = {
  id: number;
  phone: string;
  scheduled_at: string;
  status: string;
  appointment_type_id: string | null;
  video_link: string | null;
};

const STATUS_STYLES: Record<string, string> = {
  booked: "bg-success-tint text-success",
  cancelled: "bg-error-tint text-error",
  rescheduled: "bg-clay-100 text-clay-700",
  attended: "bg-success-tint text-success",
  no_show: "bg-error-tint text-error",
};
const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled", attended: "Attended", no_show: "No-show",
};

// Item 4 (Spec.md Section 0): a specific doctor's own appointments for
// today, within the existing shared staff portal -- no separate doctor
// login exists, so this is just a scoped view any staff member can open.
export function DoctorTodayAppointments({ doctorId }: { doctorId: string }) {
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/doctors/${doctorId}/appointments/today`);
    if (result.ok) setAppointments((result.data as { appointments: Appointment[] }).appointments);
  }, [doctorId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="rounded-lg border border-line bg-paper p-space-3">
      <p className="text-label mb-space-2 font-semibold text-ink-900">Today&apos;s appointments</p>
      {appointments === null ? (
        <p className="text-hint">Loading…</p>
      ) : appointments.length === 0 ? (
        <p className="text-hint">Nothing scheduled today.</p>
      ) : (
        <ul className="space-y-space-1">
          {appointments.map((a) => (
            <li key={a.id} className="rounded-md bg-card px-space-3 py-space-2 text-[12.5px]">
              <div className="flex items-center justify-between">
                <span className="tabular-nums text-ink-900">{formatTimeOnly(a.scheduled_at)}</span>
                <span className="text-ink-600">{a.phone}</span>
                <span className={cn("rounded-full px-space-2 py-0.5 text-[11px] font-semibold", STATUS_STYLES[a.status] || "bg-black/[0.04] text-ink-600")}>
                  {STATUS_LABELS[a.status] || a.status}
                </span>
              </div>
              {/* Tele-consultation Phase 2 (confirmed with the user
                  directly): this portal view is the doctor's own way to get
                  the video link -- there's no separate doctor login or
                  notification channel in this app. Only shown for a
                  tele-consultation row that actually has one. */}
              {a.appointment_type_id === "tele" && a.video_link && (
                <a
                  href={a.video_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-space-1 inline-flex items-center gap-1 text-[12px] font-semibold text-brand-600 hover:underline"
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
