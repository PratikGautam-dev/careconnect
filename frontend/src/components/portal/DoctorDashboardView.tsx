"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarCheck, CheckCircle2, Clock, History, ListChecks, MoreVertical, PlayCircle, Video } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AVATAR_TINTS, STATUS_LABELS, STATUS_STYLES, TYPE_ICONS, initials } from "@/app/portal/appointments/_components/appointments-columns";
import { TYPE_LABELS } from "@/hooks/useAppointments";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { QuickActionList, type QuickAction } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { TodayScheduleTimeline } from "@/components/portal/TodayScheduleTimeline";
import { WeeklyTrendChart } from "@/components/portal/WeeklyTrendChart";
import { AppointmentCalendar } from "@/components/doctor/AppointmentCalendar";
import { cn } from "@/lib/cn";
import { formatHeaderDateNoYear } from "@/lib/formatDate";
import { staffFetch } from "@/lib/staffAuth";

const DELAY_PRESETS = [10, 15, 30, 45, 60];

type Appointment = {
  id: number;
  phone: string;
  patient_display_id: string | null;
  department_name: string;
  scheduled_at: string;
  status: string;
  reference_id: string | null;
  appointment_type_id: string | null;
  video_link: string | null;
};

type Insights = {
  new_patients_this_week: number;
  new_patients_this_week_delta_pct: number | null;
  follow_ups_this_week: number;
  follow_ups_this_week_delta_pct: number | null;
  // No prescriptions table or consult-duration capture anywhere in this
  // app yet -- null renders as "—" rather than a made-up number (see
  // get_doctor_patient_insights()'s own docstring on the backend).
  prescriptions_issued_this_week: number | null;
  avg_consult_minutes: number | null;
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
  weekly_counts: { date: string; label: string; count: number }[];
  insights: Insights;
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

// Same reasoning as PortalDashboardPage's own polling -- no websocket/SSE
// infra, so a doctor's numbers only update on a manual refresh otherwise.
const POLL_INTERVAL_MS = 20_000;

/** This doctor's own dashboard content -- shared by the doctor branch of
 * /portal/dashboard and the legacy (unrouted) /doctor/dashboard page.
 * Self-fetches /api/doctor/dashboard; the caller owns auth/guard/shell. */
export function DoctorDashboardView() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // "Running late" -- shifts every remaining still-booked appointment today
  // forward by the chosen number of minutes, with an automated WhatsApp
  // message sent to each affected patient (backend: POST /api/doctor/
  // appointments/delay -- already doctor_id-scoped via the caller's own
  // token, unchanged from the legacy /doctor/appointments page).
  const [delayPanelOpen, setDelayPanelOpen] = useState(false);
  const [delayMinutes, setDelayMinutes] = useState("15");
  const [delaying, setDelaying] = useState(false);
  const [delayResult, setDelayResult] = useState<string | null>(null);
  const [delayError, setDelayError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/doctor/dashboard");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setData(result.data as DashboardData);
  }, [router]);

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  async function handleDelay() {
    const minutes = Number(delayMinutes);
    if (!minutes || minutes < 1) return;
    setDelaying(true);
    setDelayError(null);
    setDelayResult(null);
    const result = await staffFetch("/api/doctor/appointments/delay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutes }),
    });
    setDelaying(false);
    if (!result.ok) {
      setDelayError(result.unauthorized ? "Session expired — please log in again." : result.error);
      return;
    }
    const delayed = result.data as { notified: number };
    setDelayResult(
      delayed.notified === 0
        ? "No remaining appointments today to shift."
        : `Shifted ${delayed.notified} appointment${delayed.notified === 1 ? "" : "s"} and notified ${
            delayed.notified === 1 ? "the patient" : "each patient"
          } on WhatsApp.`,
    );
    load();
  }

  return (
    <>
      <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
        <div>
          <h1 className="text-display">Dashboard</h1>
          <p className="text-body">{formatHeaderDateNoYear(new Date())}</p>
        </div>
        <Button variant="secondary" size="md" onClick={() => setDelayPanelOpen((v) => !v)}>
          <Clock size={15} /> Running late?
        </Button>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {delayPanelOpen && (
        <Card className="mb-space-5 p-space-4">
          <p className="mb-space-1 text-[13.5px] font-semibold text-ink-900">Push back today&apos;s remaining appointments</p>
          <p className="mb-space-3 text-[12.5px] text-ink-600">
            Every still-confirmed appointment later today shifts forward by this many minutes, and each patient gets a
            WhatsApp message with their new time automatically.
          </p>
          <div className="flex flex-wrap items-center gap-space-2">
            {DELAY_PRESETS.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setDelayMinutes(String(m))}
                className={cn(
                  "h-9 rounded-md border px-space-3 text-[12.5px] font-semibold transition-colors duration-150",
                  delayMinutes === String(m)
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-line bg-card text-ink-600 hover:border-brand-300",
                )}
              >
                {m} min
              </button>
            ))}
            <Input
              type="number"
              min={1}
              max={240}
              value={delayMinutes}
              onChange={(e) => setDelayMinutes(e.target.value)}
              className="w-24"
            />
            <Button size="md" onClick={handleDelay} disabled={delaying}>
              {delaying ? "Shifting…" : "Confirm delay"}
            </Button>
          </div>
          {delayError && <p className="mt-space-2 text-[12.5px] text-error">{delayError}</p>}
          {delayResult && <p className="mt-space-2 text-[12.5px] font-semibold text-success">{delayResult}</p>}
        </Card>
      )}

      {!data ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : (
        <DashboardBody data={data} />
      )}
    </>
  );
}

const quickActions: QuickAction[] = [
  { label: "Start Consultation", icon: PlayCircle, href: "/portal/appointments" },
  // No dedicated "waiting queue" concept exists in this app -- both this and
  // "Start Consultation" open the same doctor-scoped appointments list
  // (which already reads as a queue: today's still-booked appointments in
  // order), not two separate real destinations.
  { label: "View Queue", icon: ListChecks, href: "/portal/appointments" },
  { label: "Patient History", icon: History, href: "/portal/patients" },
];

function DashboardBody({ data }: { data: DashboardData }) {
  const todayByTime = [...data.today_appointments].sort(
    (a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime(),
  );
  const teleconsultationsToday = data.today_appointments.filter((a) => a.appointment_type_id === "tele").length;
  const { insights } = data;

  return (
    <>
      <div className="mb-space-5 grid grid-cols-1 gap-space-4 xs:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Today's appointments" value={data.stats.today_appointments} deltaPct={null} hint=""
          icon={CalendarCheck} tint="brand" href="/portal/appointments"
        />
        <StatTile
          label="Completed" value={data.stats.attended_today} deltaPct={null} hint=""
          icon={CheckCircle2} tint="success" href="/portal/appointments"
        />
        <StatTile
          label="Pending consultations" value={data.stats.confirmed_today} deltaPct={null} hint=""
          icon={Clock} tint="clay" href="/portal/appointments"
        />
        <StatTile
          label="Teleconsultations" value={teleconsultationsToday} deltaPct={null} hint=""
          icon={Video} tint="brand" href="/portal/appointments"
        />
      </div>

      <div className="mb-space-5 grid grid-cols-1 gap-space-4 lg:grid-cols-3">
        <Card className="p-space-4 lg:col-span-2">
          <div className="mb-space-3 flex items-center justify-between">
            <h3 className="text-label font-bold text-ink-900">Today&apos;s appointments</h3>
            <Link href="/portal/appointments" className="text-[12.5px] font-semibold text-brand-600 hover:underline">
              View all →
            </Link>
          </div>
          {todayByTime.length === 0 ? (
            <p className="py-space-4 text-center text-[13px] text-ink-400">Nothing scheduled for today.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13.5px]">
                <thead>
                  <tr className="border-b border-line text-left text-label text-ink-400">
                    <th className="py-space-2 pr-space-3 font-medium">Time</th>
                    <th className="py-space-2 pr-space-3 font-medium">Patient</th>
                    <th className="py-space-2 pr-space-3 font-medium">Type</th>
                    <th className="py-space-2 pr-space-3 font-medium">Status</th>
                    <th className="py-space-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {todayByTime.map((a) => {
                    const TypeIcon = (a.appointment_type_id && TYPE_ICONS[a.appointment_type_id]) || CalendarCheck;
                    return (
                      <tr key={a.id} className="border-b border-line last:border-0">
                        <td className="whitespace-nowrap py-space-3 pr-space-3 tabular-nums text-ink-600">
                          {formatTime(a.scheduled_at)}
                        </td>
                        <td className="py-space-3 pr-space-3">
                          <div className="flex items-center gap-space-2">
                            <span
                              className={cn(
                                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10.5px] font-bold",
                                AVATAR_TINTS[a.id % AVATAR_TINTS.length],
                              )}
                            >
                              {initials(a.patient_display_id, a.phone)}
                            </span>
                            <span className="truncate font-semibold text-ink-900">{a.patient_display_id || a.phone}</span>
                          </div>
                        </td>
                        <td className="py-space-3 pr-space-3">
                          <span className="inline-flex items-center gap-space-1.5 whitespace-nowrap text-ink-600">
                            <TypeIcon size={14} className="shrink-0 text-ink-400" />
                            {(a.appointment_type_id && TYPE_LABELS[a.appointment_type_id]) || "Consultation"}
                          </span>
                        </td>
                        <td className="py-space-3 pr-space-3">
                          <span
                            className={cn(
                              "whitespace-nowrap rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                              STATUS_STYLES[a.status] || "bg-black/[0.04] text-ink-600",
                            )}
                          >
                            {STATUS_LABELS[a.status] || a.status}
                          </span>
                        </td>
                        <td className="py-space-3 text-right">
                          <Link
                            href={`/portal/appointments/${a.id}`}
                            title="View appointment"
                            className="inline-flex rounded-md p-1 text-ink-400 hover:bg-black/[0.04] hover:text-ink-700"
                          >
                            <MoreVertical size={16} />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <div className="mb-space-3 flex items-center justify-between">
              <h3 className="text-label font-bold text-ink-900">Today&apos;s schedule</h3>
              <Link href="/portal/appointments" className="text-[12px] font-semibold text-brand-600 hover:underline">
                View full schedule →
              </Link>
            </div>
            <TodayScheduleTimeline appointments={todayByTime} />
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 font-bold text-ink-900">Quick actions</h3>
            <QuickActionList actions={quickActions} />
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-3">
        <WeeklyTrendChart data={data.weekly_counts} />

        <Card className="p-space-4">
          <h3 className="text-label mb-space-3 font-bold text-ink-900">Patient insights</h3>
          <div className="grid grid-cols-2 gap-space-4">
            <InsightStat label="New patients" value={insights.new_patients_this_week} deltaPct={insights.new_patients_this_week_delta_pct} />
            <InsightStat label="Follow-ups" value={insights.follow_ups_this_week} deltaPct={insights.follow_ups_this_week_delta_pct} />
            <InsightStat label="Prescriptions issued" value={insights.prescriptions_issued_this_week} deltaPct={null} unavailable />
            <InsightStat label="Avg consult time" value={insights.avg_consult_minutes} deltaPct={null} unit=" min" unavailable />
          </div>
        </Card>

        <AppointmentCalendar />
      </div>
    </>
  );
}

function InsightStat({
  label, value, deltaPct, unit = "", unavailable = false,
}: {
  label: string; value: number | null; deltaPct: number | null; unit?: string; unavailable?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="text-hint truncate">{label}</p>
      <p className="text-[18px] font-semibold text-ink-900">{value === null ? "—" : `${value.toLocaleString()}${unit}`}</p>
      <p className={cn("text-[11.5px] font-semibold", deltaPct === null ? "text-ink-400" : deltaPct >= 0 ? "text-success" : "text-error")}>
        {unavailable ? "Not tracked yet" : deltaPct === null ? "vs last week" : `${deltaPct >= 0 ? "↑" : "↓"} ${Math.abs(deltaPct)}% vs last week`}
      </p>
    </div>
  );
}
