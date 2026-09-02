"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Clock, Search, Video } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { DoctorShell } from "@/components/doctor/DoctorShell";
import { useDoctorGuard } from "@/components/doctor/useDoctorGuard";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import { staffFetch } from "@/lib/staffAuth";

type Appointment = {
  id: number;
  phone: string;
  department_name: string;
  scheduled_at: string;
  status: string;
  reference_id: string | null;
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
const STATUS_FILTERS = ["all", "booked", "attended", "no_show", "cancelled", "rescheduled"] as const;
const TIME_TABS = ["upcoming", "past"] as const;
const DELAY_PRESETS = [10, 15, 30, 45, 60];

export default function DoctorAppointmentsPage() {
  const { doctor, ready } = useDoctorGuard();
  const router = useRouter();
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [dateFilter, setDateFilter] = useState("");
  const [timeTab, setTimeTab] = useState<(typeof TIME_TABS)[number]>("upcoming");

  // "Running late" -- shifts every remaining still-booked appointment today
  // forward by the chosen number of minutes, with an automated WhatsApp
  // message sent to each affected patient (backend: POST /api/doctor/
  // appointments/delay).
  const [delayPanelOpen, setDelayPanelOpen] = useState(false);
  const [delayMinutes, setDelayMinutes] = useState("15");
  const [delaying, setDelaying] = useState(false);
  const [delayResult, setDelayResult] = useState<string | null>(null);
  const [delayError, setDelayError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/doctor/appointments");
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

  const filtered = useMemo(() => {
    if (!appointments) return [];
    const now = Date.now();
    const q = searchQuery.trim().toLowerCase();
    return appointments.filter((a) => {
      const isPast = new Date(a.scheduled_at).getTime() < now;
      if (timeTab === "upcoming" && isPast) return false;
      if (timeTab === "past" && !isPast) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (dateFilter && !a.scheduled_at.startsWith(dateFilter)) return false;
      if (!q) return true;
      return (
        a.phone.toLowerCase().includes(q)
        || (a.patient_display_id || "").toLowerCase().includes(q)
        || (a.reference_id || "").toLowerCase().includes(q)
      );
    });
  }, [appointments, searchQuery, statusFilter, dateFilter, timeTab]);

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
    const data = result.data as { notified: number };
    setDelayResult(
      data.notified === 0
        ? "No remaining appointments today to shift."
        : `Shifted ${data.notified} appointment${data.notified === 1 ? "" : "s"} and notified ${data.notified === 1 ? "the patient" : "each patient"} on WhatsApp.`,
    );
    load();
  }

  if (!ready) return null;

  return (
    <DoctorShell doctor={doctor} active="appointments">
      <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
        <h1 className="text-display">Appointments</h1>
        <Button variant="secondary" size="md" onClick={() => setDelayPanelOpen((v) => !v)}>
          <Clock size={15} /> Running late?
        </Button>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      {delayPanelOpen && (
        <Card className="mb-space-4 p-space-4">
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
                  delayMinutes === String(m) ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-card text-ink-600 hover:border-brand-300",
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

      <div className="mb-space-4 flex flex-wrap items-center gap-space-2">
        {TIME_TABS.map((tTab) => (
          <button
            key={tTab}
            type="button"
            onClick={() => setTimeTab(tTab)}
            className={cn(
              "rounded-md px-space-3 py-space-2 text-[12.5px] font-semibold capitalize transition-colors duration-150",
              timeTab === tTab ? "bg-brand-600 text-white" : "bg-card text-ink-600 hover:bg-black/[0.04]",
            )}
          >
            {tTab}
          </button>
        ))}
      </div>

      <div className="mb-space-4 flex flex-wrap items-center gap-space-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="pointer-events-none absolute left-space-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search phone, patient ID, or reference…"
            className="pl-9"
          />
        </div>
        <Input type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} className="w-40" />
        {dateFilter && (
          <button type="button" onClick={() => setDateFilter("")} className="text-[12px] font-semibold text-ink-400 hover:text-ink-700">
            Clear date
          </button>
        )}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as (typeof STATUS_FILTERS)[number])}
          className="h-11 rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All statuses" : STATUS_LABELS[s] || s}
            </option>
          ))}
        </select>
      </div>

      {!appointments ? (
        <p className="text-[13px] text-ink-400">Loading…</p>
      ) : filtered.length === 0 ? (
        <Card className="p-space-6 text-center">
          <p className="text-body">No {timeTab} appointments match.</p>
        </Card>
      ) : (
        <div className="space-y-space-2">
          {filtered.map((a) => (
            <Link key={a.id} href={`/doctor/appointments/${a.id}`}>
              <Card elevation="interactive" className="flex flex-wrap items-center gap-space-3 p-space-4">
                <div className="w-40 shrink-0 text-[13px] text-ink-900">{formatShortDateTime(a.scheduled_at)}</div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-semibold text-ink-900">
                    {a.patient_display_id || a.phone}
                  </p>
                  <p className="truncate text-[12.5px] text-ink-600">{a.department_name}</p>
                </div>
                {a.reference_id && <span className="hidden shrink-0 text-[12px] text-ink-400 sm:inline">{a.reference_id}</span>}
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
              </Card>
            </Link>
          ))}
        </div>
      )}
    </DoctorShell>
  );
}
