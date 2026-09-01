"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Video } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";
import { cn } from "@/lib/cn";
import { staffFetch } from "@/lib/staffAuth";

type Appointment = {
  id: number;
  phone: string;
  department_name: string;
  scheduled_at: string;
  status: string;
  patient_display_id: string | null;
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

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export default function DoctorDashboardPage() {
  const { doctor, ready } = useDoctorGuard();
  const router = useRouter();
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/doctor/appointments/today");
    if (!result.ok) {
      if (result.unauthorized) router.push("/doctor/login");
      else setError(result.error);
      return;
    }
    setAppointments((result.data as { appointments: Appointment[] }).appointments);
  }, [router]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="dashboard">
      <div className="mb-space-5">
        <h1 className="text-display">Today&apos;s appointments</h1>
        <p className="text-body">
          {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
        </p>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {appointments === null ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : appointments.length === 0 ? (
        <Card className="p-space-6 text-center">
          <p className="text-body">Nothing scheduled for today.</p>
        </Card>
      ) : (
        <div className="space-y-space-2">
          {appointments.map((a) => (
            <Link key={a.id} href={`/doctor/appointments/${a.id}`}>
              <Card elevation="interactive" className="flex items-center gap-space-4 p-space-4">
                <div className="w-16 shrink-0 tabular-nums text-[14px] font-semibold text-ink-900">
                  {formatTime(a.scheduled_at)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-semibold text-ink-900">
                    {a.patient_display_id || a.phone}
                  </p>
                  <p className="truncate text-[12.5px] text-ink-600">{a.department_name}</p>
                </div>
                {a.appointment_type_id === "tele" && a.video_link && (
                  <Video size={16} className="shrink-0 text-brand-600" />
                )}
                <span
                  className={cn(
                    "shrink-0 rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                    STATUS_STYLES[a.status] || "bg-black/[0.04] text-ink-600",
                  )}
                >
                  {STATUS_LABELS[a.status] || a.status}
                </span>
                <ChevronRight size={16} className="shrink-0 text-ink-400" />
              </Card>
            </Link>
          ))}
        </div>
      )}
    </DoctorShell>
  );
}
