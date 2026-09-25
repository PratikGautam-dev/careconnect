"use client";

import { useState } from "react";
import {
  BarChart3,
  Briefcase,
  CheckCircle2,
  Clock,
  Coffee,
  LogIn,
  LogOut,
  Play,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatDateTime, formatHeaderDateDayMonth, formatTimeOnly } from "@/lib/formatDate";
import { portalFetch } from "@/lib/portalAuth";
import { usePermission } from "@/lib/staffAuth";
import { usePortalAttendanceToday, type AttendanceRecord } from "@/hooks/usePortalAttendanceToday";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/cn";
import {
  DEFAULT_REFERENCE_DAY_MINUTES,
  HISTORY_STATUS_LABELS,
  HISTORY_STATUS_STYLES,
  type CheckInHistoryStatus,
} from "./check-in-out-mock";

type ActivityEventKind = "check_in" | "break_start" | "current_session";
type ActivityEvent = { time: string; kind: ActivityEventKind; title: string; subtitle: string };

const EMPTY_HISTORY: AttendanceRecord[] = [];

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
    {
      time: formatTimeOnly(record.check_in_at),
      kind: "check_in",
      title: "Check in",
      subtitle: "You checked in to the hospital",
    },
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
  const {
    data: attendanceData,
    loaded,
    refetch: reloadAttendance,
  } = usePortalAttendanceToday(ready && canView);
  const today = attendanceData?.today ?? null;
  const history = attendanceData?.history ?? EMPTY_HISTORY;
  const [busy, setBusy] = useState(false);
  const [checkInModal, setCheckInModal] = useState<AttendanceRecord | null>(null);

  async function runAction(path: string, body?: object) {
    setBusy(true);
    const position = path === "/api/portal/attendance/check-in" ? await getPosition() : null;
    const result = await portalFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        body ?? (position ? { latitude: position.latitude, longitude: position.longitude } : {}),
      ),
    });
    setBusy(false);
    if (!result.ok) {
      toast.error(
        "That didn't go through",
        result.unauthorized ? "Please sign in again." : result.error,
      );
      return;
    }
    await reloadAttendance();
    if (path === "/api/portal/attendance/check-in") {
      setCheckInModal((result.data as { record: AttendanceRecord }).record);
    }
  }

  if (!ready) return null;

  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="check-in-out">
        <p className="text-ink-400 text-[13px]">
          You don&apos;t have access to Check-in / Check-out.
        </p>
      </PortalShell>
    );
  }

  const activity = buildTodaysActivity(today);
  const isCheckedIn = !!today?.check_in_at && !today?.check_out_at;
  const onBreak = !!today?.break_started_at;
  const currentStatus = !today?.check_in_at
    ? "Not checked in"
    : today.check_out_at
      ? "Checked out"
      : onBreak
        ? "On break"
        : "Checked in";
  const currentStatusStyle = !today?.check_in_at
    ? "bg-black/4 text-ink-600"
    : today.check_out_at
      ? "bg-brand-50 text-brand-600"
      : onBreak
        ? "bg-clay-100 text-clay-700"
        : "bg-success-tint text-success";
  const currentStatusDotStyle = !today?.check_in_at
    ? "bg-ink-400"
    : today.check_out_at
      ? "bg-brand-600"
      : onBreak
        ? "bg-clay-700"
        : "bg-success";
  const workingMinutes = today?.working_minutes || 0;
  const ringPercent = Math.min(
    100,
    Math.round((workingMinutes / DEFAULT_REFERENCE_DAY_MINUTES) * 100),
  );
  const historyRows = history.map(toHistoryRow);

  return (
    <PortalShell hospital={hospital} active="check-in-out">
      <PageHeader title="Check-in / Check-out" description={formatHeaderDateDayMonth(new Date())} />

      <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <User size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Current status</p>
              <p
                className={cn(
                  "text-[22px] leading-tight font-bold",
                  isCheckedIn ? "text-success" : "text-ink-900",
                )}
              >
                {currentStatus}
              </p>
              {today?.check_in_at && (
                <p className="mt-space-0.5 gap-space-1 text-ink-400 flex items-center text-[11.5px]">
                  <span className="bg-success h-1.5 w-1.5 rounded-full" /> Since{" "}
                  {formatTimeOnly(today.check_in_at)}
                </p>
              )}
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <Clock size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Check-in time</p>
              <p className="text-ink-900 text-[22px] leading-tight font-bold">
                {today?.check_in_at ? formatTimeOnly(today.check_in_at) : "-"}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <Coffee size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Break taken</p>
              <p className="text-ink-900 text-[22px] leading-tight font-bold">
                {formatMinutes(today?.break_minutes ?? 0)}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <BarChart3 size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Working hours</p>
              <p className="text-ink-900 text-[22px] leading-tight font-bold">
                {formatMinutes(workingMinutes)}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-space-4 gap-space-4 grid grid-cols-1 lg:grid-cols-2">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 text-ink-900 font-bold">Today&apos;s activity</h3>
          {!loaded ? (
            <p className="text-ink-400 text-[12.5px]">Loading…</p>
          ) : activity.length === 0 ? (
            <p className="text-ink-400 text-[12.5px]">No activity yet today.</p>
          ) : (
            <ul className="space-y-space-4">
              {activity.map((event, i) => {
                const Icon = ACTIVITY_ICONS[event.kind];
                return (
                  <li key={`${event.time}-${event.kind}`} className="gap-space-3 flex">
                    <div className="pt-space-1 flex w-16 shrink-0 flex-col items-end">
                      <span className="text-ink-400 text-[11.5px] font-medium">{event.time}</span>
                    </div>
                    <div className="flex flex-col items-center">
                      <span
                        className={cn(
                          "h-2.5 w-2.5 rounded-full",
                          i === activity.length - 1 ? "bg-success" : "bg-ink-300",
                        )}
                      />
                      {i < activity.length - 1 && (
                        <span className="mt-space-1 bg-line w-px flex-1" />
                      )}
                    </div>
                    <div className="gap-space-3 bg-brand-50/40 p-space-3 pt-space-2 flex flex-1 items-start rounded-md">
                      <span className="bg-brand-50 text-brand-600 flex h-9 w-9 shrink-0 items-center justify-center rounded-md">
                        <Icon size={16} strokeWidth={2} />
                      </span>
                      <div className="min-w-0">
                        <p className="text-ink-900 text-[13px] font-bold">{event.title}</p>
                        <p className="text-ink-400 text-[12px]">{event.subtitle}</p>
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
            <h3 className="text-label text-ink-900 font-bold">Live work timer</h3>
            {isCheckedIn && (
              <span className="gap-space-1 text-success flex items-center text-[12px] font-semibold">
                <span className="bg-success h-1.5 w-1.5 rounded-full" />{" "}
                {onBreak ? "On break" : "Currently working"}
              </span>
            )}
          </div>
          <div className="gap-space-4 flex flex-wrap items-center">
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
                <span className="mb-space-1 bg-brand-50 text-brand-600 flex h-9 w-9 items-center justify-center rounded-md">
                  <Briefcase size={18} strokeWidth={2} />
                </span>
                <span className="text-ink-900 text-[24px] leading-none font-bold">
                  {formatMinutes(workingMinutes)}
                </span>
                <span className="mt-space-1 text-ink-400 text-[11.5px]">Working today</span>
              </div>
            </div>
            <div className="space-y-space-2 flex-1">
              <div className="gap-space-3 bg-paper p-space-3 flex items-center rounded-md">
                <LogIn size={16} strokeWidth={2} className="text-ink-400 shrink-0" />
                <div>
                  <p className="text-ink-400 text-[11.5px]">Check-in time</p>
                  <p className="text-ink-900 text-[13px] font-bold">
                    {today?.check_in_at ? formatTimeOnly(today.check_in_at) : "-"}
                  </p>
                </div>
              </div>
              <div className="gap-space-3 bg-paper p-space-3 flex items-center rounded-md">
                <Coffee size={16} strokeWidth={2} className="text-ink-400 shrink-0" />
                <div>
                  <p className="text-ink-400 text-[11.5px]">Break taken</p>
                  <p className="text-ink-900 text-[13px] font-bold">
                    {formatMinutes(today?.break_minutes ?? 0)}
                  </p>
                </div>
              </div>
              <div className="gap-space-3 bg-paper p-space-3 flex items-center rounded-md">
                <Clock size={16} strokeWidth={2} className="text-ink-400 shrink-0" />
                <div>
                  <p className="text-ink-400 text-[11.5px]">Status</p>
                  <p className="text-ink-900 text-[13px] font-bold">
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

      <div className="mt-space-4 gap-space-4 grid grid-cols-1 lg:grid-cols-2">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 text-ink-900 font-bold">Quick actions</h3>
          <div className="gap-space-3 grid grid-cols-2 sm:grid-cols-4">
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/check-in")}
              disabled={!canWrite || busy || !!today?.check_in_at}
              className="gap-space-2 bg-brand-600 py-space-4 hover:bg-brand-700 flex flex-col items-center rounded-md text-white shadow-[var(--shadow-sm)] transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <LogIn size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Check In</span>
            </button>
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/break/start")}
              disabled={!canWrite || busy || !isCheckedIn || onBreak}
              className="gap-space-2 border-line bg-card py-space-4 text-ink-900 hover:border-brand-300 hover:bg-brand-50 flex flex-col items-center rounded-md border transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Coffee size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Start Break</span>
            </button>
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/break/end")}
              disabled={!canWrite || busy || !onBreak}
              className="gap-space-2 border-line bg-card py-space-4 text-ink-900 hover:border-brand-300 hover:bg-brand-50 flex flex-col items-center rounded-md border transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">End Break</span>
            </button>
            <button
              type="button"
              onClick={() => runAction("/api/portal/attendance/check-out")}
              disabled={!canWrite || busy || !isCheckedIn}
              className="gap-space-2 border-line bg-card py-space-4 text-ink-900 hover:border-brand-300 hover:bg-brand-50 flex flex-col items-center rounded-md border transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <LogOut size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Check Out</span>
            </button>
          </div>
          <span
            className={cn(
              "mt-space-3 gap-space-1 px-space-3 inline-flex items-center rounded-full py-1 text-[12px] font-semibold",
              currentStatusStyle,
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", currentStatusDotStyle)} />{" "}
            {currentStatus}
          </span>
        </Card>

        <Card className="p-space-4">
          <div className="mb-space-3 flex items-center justify-between">
            <h3 className="text-label text-ink-900 font-bold">Recent check-in history</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-line text-label text-ink-400 border-b text-left">
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
                    <td colSpan={5} className="py-space-4 text-ink-400 text-center">
                      No history yet.
                    </td>
                  </tr>
                )}
                {historyRows.map((r) => (
                  <tr key={r.date} className="border-line border-b last:border-0">
                    <td className="py-space-3 pr-space-3 text-ink-900 whitespace-nowrap">
                      {r.date}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {r.checkIn}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {r.checkOut ?? "-"}
                    </td>
                    <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                      {r.totalHours}
                    </td>
                    <td className="py-space-3">
                      <span
                        className={cn(
                          "px-space-2 rounded-full py-0.5 text-[11px] font-semibold whitespace-nowrap",
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
          className="p-space-4 fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setCheckInModal(null)}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            className="bg-card p-space-6 w-full max-w-[380px] rounded-lg text-center shadow-[var(--shadow-lg)]"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="mb-space-4 bg-success-tint text-success mx-auto flex h-14 w-14 items-center justify-center rounded-full">
              <CheckCircle2 size={28} strokeWidth={2} />
            </span>
            <h2 className="text-ink-900 text-[17px] font-bold">Checked In</h2>
            <p className="mt-space-1.5 text-ink-600 text-[13.5px]">
              {formatDateTime(checkInModal.check_in_at)}
            </p>
            <span
              className={cn(
                "mt-space-4 gap-space-1 px-space-3 inline-flex items-center rounded-full py-1 text-[12.5px] font-semibold",
                checkInModal.status === "late"
                  ? "bg-clay-100 text-clay-700"
                  : "bg-success-tint text-success",
              )}
            >
              {checkInModal.status === "late"
                ? `Late by ${checkInModal.late_minutes} min`
                : "On time"}
            </span>
            <Button className="mt-space-6 w-full" onClick={() => setCheckInModal(null)}>
              OK
            </Button>
          </div>
        </div>
      )}
    </PortalShell>
  );
}
