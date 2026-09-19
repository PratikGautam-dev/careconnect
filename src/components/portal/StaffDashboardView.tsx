"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  BarChart3,
  CalendarClock,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Coffee,
  LogIn,
  LogOut,
  Play,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { useHolidayApplication } from "@/hooks/useHolidayApplication";
import { formatLeaveTypeLabel, type LeaveRequestStatus, type LeaveType } from "@/hooks/useLeaveRequests";
import { formatDate, formatHeaderDateNoYear, formatTimeOnly } from "@/lib/formatDate";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/cn";

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

const REQUEST_STATUS_LABELS: Record<LeaveRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};
const REQUEST_STATUS_STYLES: Record<LeaveRequestStatus, string> = {
  pending: "bg-clay-100 text-clay-700",
  approved: "bg-success-tint text-success",
  rejected: "bg-error-tint text-error",
};

function formatMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Same "resolve to null rather than reject" contract check-in-out/page.tsx
 * already established -- a denied/unavailable geolocation still lets the
 * check-in submit, just with no coordinates for the backend's (optional)
 * geofence check. */
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

function WeeklyHoursTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { payload: { minutes: number } }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-line bg-card px-space-3 py-space-2 rounded-md border text-[12.5px] shadow-[var(--shadow-md)]">
      <p className="text-ink-900 font-semibold">{label}</p>
      <p className="text-ink-600">{formatMinutes(payload[0].payload.minutes)}</p>
    </div>
  );
}

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** This staff member's own dashboard content -- check-in status, a weekly
 * attendance chart, leave balance, a compact leave-application form, and
 * their own recent requests. Self-fetches attendance (same /api/portal/
 * attendance/today endpoint and AttendanceRecord shape check-in-out/page.tsx
 * uses) and leave data (useHolidayApplication); the caller owns auth/guard/
 * shell. Replaces the hospital-wide "Admin Dashboard" that every non-doctor,
 * non-admin staff member used to see (dashboard/page.tsx's own branch on
 * session.is_admin -- confirmed with the user staff should get a self-
 * service dashboard of their own instead). */
export function StaffDashboardView() {
  const router = useRouter();
  const [today, setToday] = useState<AttendanceRecord | null>(null);
  const [history, setHistory] = useState<AttendanceRecord[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadAttendance = useCallback(async () => {
    const result = await staffFetch("/api/portal/attendance/today");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      setLoaded(true);
      return;
    }
    const data = result.data as { today: AttendanceRecord | null; history: AttendanceRecord[] };
    setToday(data.today);
    setHistory(data.history);
    setLoaded(true);
  }, [router]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const { requests, balance, leaveTypes, submitting, submit } = useHolidayApplication(true);

  async function runAction(path: string) {
    setBusy(true);
    const position = path === "/api/portal/attendance/check-in" ? await getPosition() : null;
    const result = await staffFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(position ? { latitude: position.latitude, longitude: position.longitude } : {}),
    });
    setBusy(false);
    if (!result.ok) {
      toast.error("That didn't go through", result.unauthorized ? "Please sign in again." : result.error);
      return;
    }
    await loadAttendance();
  }

  const isCheckedIn = !!today?.check_in_at && !today?.check_out_at;
  const onBreak = !!today?.break_started_at;
  const currentStatus = !today?.check_in_at
    ? "Not checked in"
    : today.check_out_at
      ? "Checked out"
      : onBreak
        ? "On break"
        : "Checked in";
  const workingMinutes = today?.working_minutes || 0;
  const pendingCount = (requests || []).filter((r) => r.status === "pending").length;

  const weeklyHours = useMemo(() => {
    const byDate = new Map(history.map((h) => [h.date, h]));
    const days: { date: string; label: string; minutes: number; hours: number }[] = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = dateKey(d);
      const minutes = byDate.get(key)?.working_minutes || 0;
      days.push({
        date: key,
        label: WEEKDAY_LABELS[d.getDay()],
        minutes,
        hours: Math.round((minutes / 60) * 100) / 100,
      });
    }
    return days;
  }, [history]);

  // Recent-requests table + mini calendar both need "which dates fall
  // inside a still-relevant (not rejected) request, and what status" --
  // computed once here from the same `requests` list.
  const leaveDatesByStatus = useMemo(() => {
    const map = new Map<string, LeaveRequestStatus>();
    for (const r of requests || []) {
      if (r.status === "rejected") continue;
      const from = new Date(`${r.from_date}T00:00:00`);
      const to = new Date(`${r.to_date}T00:00:00`);
      for (let d = from; d <= to; d.setDate(d.getDate() + 1)) {
        map.set(dateKey(d), r.status);
      }
    }
    return map;
  }, [requests]);

  const [leaveType, setLeaveType] = useState<LeaveType>("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  // leaveTypes only arrives after useHolidayApplication's own fetch
  // resolves -- a derived fallback rather than syncing it into state via an
  // effect, same pattern NewLeaveRequestDialog.tsx already established.
  const selectedLeaveType = leaveType || leaveTypes[0] || "";

  async function handleApply(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!selectedLeaveType) {
      setFormError("Please select a leave type.");
      return;
    }
    if (!fromDate || !toDate) {
      setFormError("Both From date and To date are required.");
      return;
    }
    if (toDate < fromDate) {
      setFormError("To date can't be before From date.");
      return;
    }
    if (!reason.trim()) {
      setFormError("Please enter a reason for leave.");
      return;
    }
    const err = await submit({
      leave_type: selectedLeaveType,
      from_date: fromDate,
      to_date: toDate,
      is_half_day: false,
      reason: reason.trim(),
    });
    if (err) {
      setFormError(err);
      return;
    }
    setLeaveType("");
    setFromDate("");
    setToDate("");
    setReason("");
  }

  const recentRequests = (requests || []).slice(0, 5);

  return (
    <>
      <div className="mb-space-5 gap-space-3 flex flex-wrap items-center justify-between">
        <div>
          <h1 className="text-display">Staff Dashboard</h1>
          <p className="text-body">{formatHeaderDateNoYear(new Date())}</p>
        </div>
      </div>

      <div className="mb-space-5 gap-space-4 xs:grid-cols-2 grid grid-cols-1 lg:grid-cols-4">
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <User size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Today&apos;s status</p>
              <p
                className={cn(
                  "text-[19px] leading-tight font-bold",
                  isCheckedIn ? "text-success" : "text-ink-900",
                )}
              >
                {loaded ? currentStatus : "…"}
              </p>
              {today?.check_in_at && (
                <p className="mt-space-0.5 text-ink-400 text-[11.5px]">
                  Since {formatTimeOnly(today.check_in_at)}
                </p>
              )}
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <BarChart3 size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Working hours today</p>
              <p className="text-ink-900 text-[19px] leading-tight font-bold">
                {formatMinutes(workingMinutes)}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <CalendarDays size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Leave balance</p>
              <p className="text-ink-900 text-[19px] leading-tight font-bold">
                {balance ? `${balance.remaining_days} days` : "…"}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-space-4">
          <div className="gap-space-3 flex items-center">
            <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
              <CalendarClock size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label text-ink-600 truncate font-medium">Pending applications</p>
              <p className="text-ink-900 text-[19px] leading-tight font-bold">
                {requests === null ? "…" : pendingCount}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <div className="mb-space-5 gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <Card className="p-space-4 lg:col-span-2">
          <h3 className="text-label mb-space-4 text-ink-900 font-bold">Attendance (this week)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={weeklyHours} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="#e1e0d9" vertical={false} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: "#c3c2b7" }}
                tick={{ fontSize: 12, fill: "#898781" }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: "#898781" }}
                allowDecimals={false}
                unit="h"
              />
              <Tooltip content={<WeeklyHoursTooltip />} cursor={{ fill: "#00949E", fillOpacity: 0.08 }} />
              <Bar dataKey="hours" fill="#00949E" radius={[4, 4, 0, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <MiniLeaveCalendar leaveDatesByStatus={leaveDatesByStatus} />
      </div>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 text-ink-900 font-bold">Check-in / Check-out</h3>
          <div className="mb-space-3 gap-space-3 grid grid-cols-3 text-center">
            <div>
              <p className="text-hint">Check-in</p>
              <p className="text-ink-900 text-[13.5px] font-bold">
                {today?.check_in_at ? formatTimeOnly(today.check_in_at) : "-"}
              </p>
            </div>
            <div>
              <p className="text-hint">Break</p>
              <p className="text-ink-900 text-[13.5px] font-bold">
                {formatMinutes(today?.break_minutes ?? 0)}
              </p>
            </div>
            <div>
              <p className="text-hint">Total today</p>
              <p className="text-ink-900 text-[13.5px] font-bold">{formatMinutes(workingMinutes)}</p>
            </div>
          </div>
          <div className="gap-space-2 grid grid-cols-2">
            <Button
              size="md"
              onClick={() => runAction("/api/portal/attendance/check-in")}
              disabled={busy || !!today?.check_in_at}
            >
              <LogIn size={14} /> Check In
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => runAction("/api/portal/attendance/check-out")}
              disabled={busy || !isCheckedIn}
            >
              <LogOut size={14} /> Check Out
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => runAction("/api/portal/attendance/break/start")}
              disabled={busy || !isCheckedIn || onBreak}
            >
              <Coffee size={14} /> Start Break
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => runAction("/api/portal/attendance/break/end")}
              disabled={busy || !onBreak}
            >
              <Play size={14} /> End Break
            </Button>
          </div>
          <p className="text-hint mt-space-2 text-center">
            <Link href="/portal/check-in-out" className="text-brand-600 font-semibold hover:underline">
              Full check-in / check-out page →
            </Link>
          </p>
        </Card>

        <Card className="p-space-4">
          <h3 className="text-label mb-space-3 text-ink-900 font-bold">Holiday Application</h3>
          <form onSubmit={handleApply} className="gap-space-3 grid grid-cols-1">
            <Field label="Leave type" htmlFor="dash_leave_type" required>
              <select
                id="dash_leave_type"
                value={selectedLeaveType}
                onChange={(e) => setLeaveType(e.target.value)}
                disabled={leaveTypes.length === 0}
                className="border-line bg-card px-space-3 text-ink-900 disabled:bg-paper disabled:text-ink-400 h-11 w-full rounded-md border text-[14px] disabled:cursor-not-allowed"
              >
                <option value="" disabled>
                  Select leave type
                </option>
                {leaveTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
            <div className="gap-x-space-3 grid grid-cols-2">
              <Field label="From date" htmlFor="dash_from_date" required>
                <Input
                  id="dash_from_date"
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                />
              </Field>
              <Field label="To date" htmlFor="dash_to_date" required>
                <Input
                  id="dash_to_date"
                  type="date"
                  value={toDate}
                  min={fromDate || undefined}
                  onChange={(e) => setToDate(e.target.value)}
                />
              </Field>
            </div>
            <Field label="Reason" htmlFor="dash_reason" required>
              <Textarea
                id="dash_reason"
                rows={2}
                placeholder="Enter reason for leave..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            {formError && <p className="text-error text-[12.5px] font-medium">{formError}</p>}
            <Button type="submit" size="md" disabled={submitting}>
              {submitting ? "Submitting…" : "Submit Application"}
            </Button>
          </form>
        </Card>

        <Card className="p-space-4">
          <div className="mb-space-3 flex items-center justify-between">
            <h3 className="text-label text-ink-900 font-bold">Recent requests</h3>
            <Link
              href="/portal/holiday-application"
              className="text-brand-600 text-[12px] font-semibold hover:underline"
            >
              View all →
            </Link>
          </div>
          {requests === null ? (
            <p className="text-ink-400 text-[12.5px]">Loading…</p>
          ) : recentRequests.length === 0 ? (
            <p className="text-ink-400 text-[12.5px]">No leave requests yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-line text-label text-ink-400 border-b text-left">
                    <th className="py-space-2 pr-space-2 font-medium">Leave type</th>
                    <th className="py-space-2 pr-space-2 font-medium">From – To</th>
                    <th className="py-space-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentRequests.map((r) => (
                    <tr key={r.id} className="border-line border-b last:border-0">
                      <td className="py-space-2.5 pr-space-2 text-ink-900 whitespace-nowrap">
                        {formatLeaveTypeLabel(r.leave_type)}
                      </td>
                      <td className="py-space-2.5 pr-space-2 text-ink-600 whitespace-nowrap">
                        {formatDate(r.from_date)} – {formatDate(r.to_date)}
                      </td>
                      <td className="py-space-2.5">
                        <span
                          className={cn(
                            "px-space-2 rounded-full py-0.5 text-[10.5px] font-semibold whitespace-nowrap",
                            REQUEST_STATUS_STYLES[r.status],
                          )}
                        >
                          {REQUEST_STATUS_LABELS[r.status]}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

/** Static-month calendar (no month navigation beyond prev/next/today) --
 * marks today with a ring and any date inside a still-relevant (pending or
 * approved) leave request with a dot, colored by that request's status.
 * Deliberately NOT PortalMiniCalendar (that one's scoped to booked
 * appointments, a different domain entirely) -- this is this staff
 * member's own leave calendar, built from data useHolidayApplication
 * already loaded, no separate fetch. */
function MiniLeaveCalendar({ leaveDatesByStatus }: { leaveDatesByStatus: Map<string, LeaveRequestStatus> }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1); // 1-12

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

  const firstOfMonth = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const leadingBlanks = firstOfMonth.getDay();
  const todayKey = dateKey(now);
  const monthLabel = firstOfMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });

  const cells: { key: string | null; day: number | null }[] = [];
  for (let i = 0; i < leadingBlanks; i++) cells.push({ key: null, day: null });
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ key: `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`, day: d });
  }

  const DOT_STYLES: Record<LeaveRequestStatus, string> = {
    pending: "bg-clay-600",
    approved: "bg-success",
    rejected: "bg-error",
  };

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
          const isToday = c.key === todayKey;
          const leaveStatus = leaveDatesByStatus.get(c.key!);
          return (
            <div
              key={c.key}
              className={cn(
                "flex aspect-square flex-col items-center justify-center gap-0.5 rounded-md border text-[12px]",
                isToday ? "border-brand-300 bg-brand-50 text-ink-900" : "border-transparent text-ink-700",
              )}
            >
              <span className="font-semibold">{c.day}</span>
              {leaveStatus && (
                <span className={cn("h-1.5 w-1.5 rounded-full", DOT_STYLES[leaveStatus])} />
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-space-3 gap-space-3 text-ink-400 flex flex-wrap items-center text-[11px]">
        <span className="gap-space-1 flex items-center">
          <span className="bg-success h-1.5 w-1.5 rounded-full" /> Approved
        </span>
        <span className="gap-space-1 flex items-center">
          <span className="bg-clay-600 h-1.5 w-1.5 rounded-full" /> Pending
        </span>
      </div>
    </Card>
  );
}
