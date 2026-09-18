"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, Briefcase, CheckCircle2, Clock, Coffee, LogIn, LogOut, Play, User } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatDateTime, formatHeaderDateDayMonth, formatTimeOnly } from "@/lib/formatDate";
import { portalFetch } from "@/lib/portalAuth";
import { usePermission } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/cn";
import {
  DEFAULT_REFERENCE_DAY_MINUTES, HISTORY_STATUS_LABELS, HISTORY_STATUS_STYLES, type CheckInHistoryStatus,
} from "./check-in-out-mock";

type AttendanceRecord = {
  date: string;
  check_in_at: string | null;
  check_out_at: string | null;
  break_started_at: string | null;
  break_minutes: number;
  status: "on_time" | "late" | "absent" | "leave" | "half_day";
  late_minutes: number;
  working_minutes: number;
  overtime_minutes: number;
  check_in_verified_method: string | null;
};

type ActivityEventKind = "check_in" | "break_start" | "current_session";
type ActivityEvent = { time: string; kind: ActivityEventKind; title: string; subtitle: string };

const ATTENDANCE_STATUS_LABELS: Record<AttendanceRecord["status"], string> = {
  on_time: "On Time",
  late: "Late",
  absent: "Absent",
  leave: "Leave",
  half_day: "Half Day",
};

const ACTIVITY_ICONS: Record<ActivityEventKind, typeof LogIn> = {
  check_in: LogIn,
  break_start: Coffee,
  current_session: Briefcase,
};

function buildTodaysActivity(record: AttendanceRecord | null): ActivityEvent[] {
  if (!record?.check_in_at) return [];
  const events: ActivityEvent[] = [
    { time: formatTimeOnly(record.check_in_at), kind: "check_in", title: "Check in", subtitle: "You checked in to the hospital" },
  ];
  if (record.break_started_at) {
    events.push({
      time: formatTimeOnly(record.break_started_at),
      kind: "break_start",
      title: "Break start",
      subtitle: "Currently on break",
    });
  } else if (!record.check_out_at) {
    events.push({
      time: formatTimeOnly(record.check_in_at),
      kind: "current_session",
      title: "Current session",
      subtitle: `Working since ${formatTimeOnly(record.check_in_at)}`,
    });
  }
  return events;
}

function formatMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
}

function toHistoryRow(record: AttendanceRecord) {
  const status: CheckInHistoryStatus = record.check_out_at ? "completed" : "in_progress";
  return {
    date: record.date,
    checkIn: record.check_in_at ? formatTimeOnly(record.check_in_at) : "-",
    checkOut: record.check_out_at ? formatTimeOnly(record.check_out_at) : null,
    totalHours: formatMinutes(record.working_minutes),
    status,
  };
}

/** Gets the browser's current position, resolving to null (rather than
 * rejecting) on denial/unavailability so callers can still submit a
 * check-in/out with no coordinates -- the backend simply skips the
 * geofence check when it receives none, same "each dimension is
 * independently optional" contract db/repositories/attendance.py's
 * check_in() already applies for a hospital that hasn't configured a
 * location at all. */
function getPosition(): Promise<{ latitude: number; longitude: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  });
}

/** /portal/check-in-out -- today's check-in/check-out activity, a live
 * working-hours ring, quick-action buttons, and recent history. Real
 * backend now (db/repositories/attendance.py + portal/routes/attendance.py):
 * Check In/Check Out/Start Break/End Break call the real endpoints, gated
 * by a hospital's own geofence/IP policy (Settings -> Attendance) when
 * configured. Gated by the real "check_in_out" page_key (migration
 * 20260914130000) -- view+write for every role except the seeded Admin
 * role by default, editable per-hospital via Settings -> Roles &
 * Permissions like any other page. */
export default function CheckInOutPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("check_in_out", "view");
  const canWrite = usePermission("check_in_out", "write");
  const [today, setToday] = useState<AttendanceRecord | null>(null);
  const [history, setHistory] = useState<AttendanceRecord[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [checkInModal, setCheckInModal] = useState<AttendanceRecord | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch("/api/portal/attendance/today");
    if (result.ok) {
      const data = result.data as { today: AttendanceRecord | null; history: AttendanceRecord[] };
      setToday(data.today);
      setHistory(data.history);
    }
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (ready && canView) load();
  }, [ready, canView, load]);

  async function runAction(path: string, body?: object) {
    setBusy(true);
    const position = path === "/api/portal/attendance/check-in" ? await getPosition() : null;
    const result = await portalFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? (position ? { latitude: position.latitude, longitude: position.longitude } : {})),
    });
    setBusy(false);
    if (!result.ok) {
      toast.error("That didn't go through", result.unauthorized ? "Please sign in again." : result.error);
      return;
    }
    await load();
    if (path === "/api/portal/attendance/check-in") {
      setCheckInModal((result.data as { record: AttendanceRecord }).record);
    }
  }

  if (!ready) return null;

  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="check-in-out">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Check-in / Check-out.</p>
      </PortalShell>
    );
  }

  const activity = buildTodaysActivity(today);
  const isCheckedIn = !!today?.check_in_at && !today?.check_out_at;
  const onBreak = !!today?.break_started_at;
  const currentStatus = !today?.check_in_at ? "Not checked in" : today.check_out_at ? "Checked out" : onBreak ? "On break" : "Checked in";
  const currentStatusStyle = !today?.check_in_at
    ? "bg-black/4 text-ink-600"
    : today.check_out_at
    ? "bg-brand-50 text-brand-600"
    : onBreak
    ? "bg-clay-100 text-clay-700"
    : "bg-success-tint text-success";
  const currentStatusDotStyle = !today?.check_in_at ? "bg-ink-400" : today.check_out_at ? "bg-brand-600" : onBreak ? "bg-clay-700" : "bg-success";
  const workingMinutes = today?.working_minutes || 0;
  const ringPercent = Math.min(100, Math.round((workingMinutes / DEFAULT_REFERENCE_DAY_MINUTES) * 100));
  const historyRows = history.map(toHistoryRow);

  return (
    <PortalShell hospital={hospital} active="check-in-out">
      <PageHeader title="Check-in / Check-out" description={formatHeaderDateDayMonth(new Date())} />

      <div className="grid grid-cols-1 gap-space-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-space-4">
          <div className="flex items-center gap-space-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <User size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label truncate font-medium text-ink-600">Current status</p>
              <p className={cn("text-[22px] font-bold leading-tight", isCheckedIn ? "text-success" : "text-ink-900")}>
                {currentStatus}
              </p>
              {today?.check_in_at && (
                <p className="mt-space-0.5 flex items-center gap-space-1 text-[11.5px] text-ink-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" /> Since {formatTimeOnly(today.check_in_at)}
                </p>
              )}
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="flex items-center gap-space-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Clock size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label truncate font-medium text-ink-600">Check-in time</p>
              <p className="text-[22px] font-bold leading-tight text-ink-900">
                {today?.check_in_at ? formatTimeOnly(today.check_in_at) : "-"}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="flex items-center gap-space-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Coffee size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label truncate font-medium text-ink-600">Break taken</p>
              <p className="text-[22px] font-bold leading-tight text-ink-900">{formatMinutes(today?.break_minutes ?? 0)}</p>
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="flex items-center gap-space-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <BarChart3 size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label truncate font-medium text-ink-600">Working hours</p>
              <p className="text-[22px] font-bold leading-tight text-ink-900">{formatMinutes(workingMinutes)}</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-space-4 grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 font-bold text-ink-900">Today&apos;s activity</h3>
          {!loaded ? (
            <p className="text-[12.5px] text-ink-400">Loading…</p>
          ) : activity.length === 0 ? (
            <p className="text-[12.5px] text-ink-400">No activity yet today.</p>
          ) : (
            <ul className="space-y-space-4">
              {activity.map((event, i) => {
                const Icon = ACTIVITY_ICONS[event.kind];
                return (
                  <li key={`${event.time}-${event.kind}`} className="flex gap-space-3">
                    <div className="flex w-16 shrink-0 flex-col items-end pt-space-1">
                      <span className="text-[11.5px] font-medium text-ink-400">{event.time}</span>
                    </div>
                    <div className="flex flex-col items-center">
                      <span className={cn("h-2.5 w-2.5 rounded-full", i === activity.length - 1 ? "bg-success" : "bg-ink-300")} />
                      {i < activity.length - 1 && <span className="mt-space-1 w-px flex-1 bg-line" />}
                    </div>
                    <div className="flex flex-1 items-start gap-space-3 rounded-md bg-brand-50/40 p-space-3 pt-space-2">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-600">
                        <Icon size={16} strokeWidth={2} />
                      </span>
                      <div className="min-w-0">
                        <p className="text-[13px] font-bold text-ink-900">{event.title}</p>
                        <p className="text-[12px] text-ink-400">{event.subtitle}</p>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card className="p-space-4">
          <div className="mb-space-4 flex items-center justify-between">
            <h3 className="text-label font-bold text-ink-900">Live work timer</h3>
            {isCheckedIn && (
              <span className="flex items-center gap-space-1 text-[12px] font-semibold text-success">
                <span className="h-1.5 w-1.5 rounded-full bg-success" /> {onBreak ? "On break" : "Currently working"}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-space-4">
            <div className="relative mx-auto h-[220px] w-[220px] shrink-0">
              <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
                <circle cx="50" cy="50" r="44" fill="none" stroke="#e9e8e2" strokeWidth="8" />
                <circle
                  cx="50"
                  cy="50"
                  r="44"
                  fill="none"
                  stroke="#00949E"
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 44}`}
                  strokeDashoffset={`${2 * Math.PI * 44 * (1 - ringPercent / 100)}`}
                />
              </svg>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="mb-space-1 flex h-9 w-9 items-center justify-center rounded-md bg-brand-50 text-brand-600">
                  <Briefcase size={18} strokeWidth={2} />
                </span>
                <span className="text-[24px] font-bold leading-none text-ink-900">{formatMinutes(workingMinutes)}</span>
                <span className="mt-space-1 text-[11.5px] text-ink-400">Working today</span>
              </div>
            </div>
            <div className="flex-1 space-y-space-2">
              <div className="flex items-center gap-space-3 rounded-md bg-paper p-space-3">
                <LogIn size={16} strokeWidth={2} className="shrink-0 text-ink-400" />
                <div>
                  <p className="text-[11.5px] text-ink-400">Check-in time</p>
                  <p className="text-[13px] font-bold text-ink-900">{today?.check_in_at ? formatTimeOnly(today.check_in_at) : "-"}</p>
                </div>
              </div>
              <div className="flex items-center gap-space-3 rounded-md bg-paper p-space-3">
                <Coffee size={16} strokeWidth={2} className="shrink-0 text-ink-400" />
                <div>
                  <p className="text-[11.5px] text-ink-400">Break taken</p>
                  <p className="text-[13px] font-bold text-ink-900">{formatMinutes(today?.break_minutes ?? 0)}</p>
                </div>
              </div>
              <div className="flex items-center gap-space-3 rounded-md bg-paper p-space-3">
                <Clock size={16} strokeWidth={2} className="shrink-0 text-ink-400" />
                <div>
                  <p className="text-[11.5px] text-ink-400">Status</p>
                  <p className="text-[13px] font-bold text-ink-900">
                    {today
                      ? `${ATTENDANCE_STATUS_LABELS[today.status]}${today.status === "late" ? ` (${today.late_minutes} min)` : ""}`
                      : "-"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-space-4 grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 font-bold text-ink-900">Quick actions</h3>
          <div className="grid grid-cols-2 gap-space-3 sm:grid-cols-4">
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/check-in")}
              disabled={!canWrite || busy || !!today?.check_in_at}
              className="flex flex-col items-center gap-space-2 rounded-md bg-brand-600 py-space-4 text-white shadow-[var(--shadow-sm)] transition-colors duration-150 hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <LogIn size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Check In</span>
            </button>
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/break/start")}
              disabled={!canWrite || busy || !isCheckedIn || onBreak}
              className="flex flex-col items-center gap-space-2 rounded-md border border-line bg-card py-space-4 text-ink-900 transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Coffee size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Start Break</span>
            </button>
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/break/end")}
              disabled={!canWrite || busy || !onBreak}
              className="flex flex-col items-center gap-space-2 rounded-md border border-line bg-card py-space-4 text-ink-900 transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">End Break</span>
            </button>
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/check-out")}
              disabled={!canWrite || busy || !isCheckedIn}
              className="flex flex-col items-center gap-space-2 rounded-md border border-line bg-card py-space-4 text-ink-900 transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <LogOut size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Check Out</span>
            </button>
          </div>
          <span
            className={cn(
              "mt-space-3 inline-flex items-center gap-space-1 rounded-full px-space-3 py-1 text-[12px] font-semibold",
              currentStatusStyle,
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", currentStatusDotStyle)} /> {currentStatus}
          </span>
        </Card>

        <Card className="p-space-4">
          <div className="mb-space-3 flex items-center justify-between">
            <h3 className="text-label font-bold text-ink-900">Recent check-in history</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-line text-left text-label text-ink-400">
                  <th className="py-space-2 pr-space-3 font-medium">Date</th>
                  <th className="py-space-2 pr-space-3 font-medium">Check-in</th>
                  <th className="py-space-2 pr-space-3 font-medium">Check-out</th>
                  <th className="py-space-2 pr-space-3 font-medium">Total hours</th>
                  <th className="py-space-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {historyRows.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-space-4 text-center text-ink-400">No history yet.</td>
                  </tr>
                )}
                {historyRows.map((r) => (
                  <tr key={r.date} className="border-b border-line last:border-0">
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-900">{r.date}</td>
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.checkIn}</td>
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.checkOut ?? "-"}</td>
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.totalHours}</td>
                    <td className="py-space-3">
                      <span
                        className={cn(
                          "whitespace-nowrap rounded-full px-space-2 py-0.5 text-[11px] font-semibold",
                          HISTORY_STATUS_STYLES[r.status],
                        )}
                      >
                        {HISTORY_STATUS_LABELS[r.status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {checkInModal?.check_in_at && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-space-4"
          onClick={() => setCheckInModal(null)}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            className="w-full max-w-[380px] rounded-lg bg-card p-space-6 text-center shadow-[var(--shadow-lg)]"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="mx-auto mb-space-4 flex h-14 w-14 items-center justify-center rounded-full bg-success-tint text-success">
              <CheckCircle2 size={28} strokeWidth={2} />
            </span>
            <h2 className="text-[17px] font-bold text-ink-900">Checked In</h2>
            <p className="mt-space-1.5 text-[13.5px] text-ink-600">{formatDateTime(checkInModal.check_in_at)}</p>
            <span
              className={cn(
                "mt-space-4 inline-flex items-center gap-space-1 rounded-full px-space-3 py-1 text-[12.5px] font-semibold",
                checkInModal.status === "late" ? "bg-clay-100 text-clay-700" : "bg-success-tint text-success",
              )}
            >
              {checkInModal.status === "late" ? `Late by ${checkInModal.late_minutes} min` : "On time"}
            </span>
            <Button className="mt-space-6 w-full" onClick={() => setCheckInModal(null)}>OK</Button>
          </div>
        </div>
      )}
    </PortalShell>
  );
}
