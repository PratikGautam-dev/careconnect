"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Video } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { StatTile } from "@/components/portal/StatTile";
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

type DashboardData = {
  stats: {
    today_appointments: number;
    confirmed_today: number;
    attended_today: number;
    no_shows_today: number;
    upcoming_appointments: number;
  };
  today_appointments: Appointment[];
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

// Same reasoning as PortalDashboardPage's own polling -- no websocket/SSE
// infra, so a doctor's numbers only update on a manual refresh otherwise.
const POLL_INTERVAL_MS = 20_000;

export default function DoctorDashboardPage() {
  const { doctor, ready } = useDoctorGuard();
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/doctor/dashboard");
    if (!result.ok) {
      if (result.unauthorized) router.push("/doctor/login");
      else setError(result.error);
      return;
    }
    setData(result.data as DashboardData);
  }, [router]);

  useEffect(() => {
    if (!ready) return;
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [ready, load]);

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="dashboard">
      <div className="mb-space-5">
        <h1 className="text-display">Dashboard</h1>
        <p className="text-body">
          {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
        </p>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {!data ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <>
          <div className="mb-space-5 grid grid-cols-1 gap-space-4 xs:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Upcoming appointments" value={data.stats.upcoming_appointments} deltaPct={null} hint="Currently booked" />
            <StatTile label="Today's appointments" value={data.stats.today_appointments} deltaPct={null} hint="" />
            <StatTile label="Attended today" value={data.stats.attended_today} deltaPct={null} hint="" />
            <StatTile label="No-shows today" value={data.stats.no_shows_today} deltaPct={null} hint="" upIsGood={false} />
          </div>

          <h2 className="mb-space-3 text-[15px] font-bold text-ink-900">Today&apos;s appointments</h2>
          {data.today_appointments.length === 0 ? (
            <Card className="p-space-6 text-center">
              <p className="text-body">Nothing scheduled for today.</p>
            </Card>
          ) : (
            <div className="space-y-space-2">
              {data.today_appointments.map((a) => (
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
        </>
      )}
    </DoctorShell>
  );
}
