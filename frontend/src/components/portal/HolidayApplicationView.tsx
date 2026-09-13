"use client";

import { useMemo, useState } from "react";
import { Calendar as CalendarIcon, CalendarDays, ChevronLeft, ChevronRight, Clock3, Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { useHolidayApplication } from "@/hooks/useHolidayApplication";
import type { LeaveRequestRow, LeaveRequestStatus, LeaveType } from "@/hooks/useLeaveRequests";
import { cn } from "@/lib/cn";

const LEAVE_TYPE_LABELS: Record<LeaveType, string> = {
  annual: "Annual Leave",
  sick: "Sick Leave",
  casual: "Casual Leave",
  maternity: "Maternity Leave",
  conference: "Conference Leave",
  personal: "Personal Leave",
};
const LEAVE_TYPES = Object.keys(LEAVE_TYPE_LABELS) as LeaveType[];

const STATUS_STYLES: Record<LeaveRequestStatus, string> = {
  pending: "bg-clay-100 text-clay-700",
  approved: "bg-success-tint text-success",
  rejected: "bg-error-tint text-error",
};
const STATUS_LABELS: Record<LeaveRequestStatus, string> = { pending: "Pending", approved: "Approved", rejected: "Rejected" };

const REASON_MAX = 500;

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function formatShort(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

/** Doctor/staff self-service leave application (migration 6eda12041ecf) --
 * submits into the SAME leave_requests table the admin Leave Requests page
 * reviews, so a submission here shows up there immediately, pending
 * approval. Not doctor-only: any signed-in staff member with the
 * "holiday_application" permission (view+write for every role by default)
 * can use this. Self-fetches /api/portal/leave-requests/mine; the caller
 * owns auth/guard/shell. */
export function HolidayApplicationView({ canWrite }: { canWrite: boolean }) {
  const { requests, balance, error, submitting, submit } = useHolidayApplication(true);

  const [leaveType, setLeaveType] = useState<LeaveType>("annual");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [duration, setDuration] = useState<"full" | "half">("full");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function resetForm() {
    setLeaveType("annual");
    setFromDate("");
    setToDate("");
    setDuration("full");
    setReason("");
    setFormError(null);
  }

  async function handleSubmit() {
    setFormError(null);
    if (!fromDate || !toDate) { setFormError("Both From date and To date are required."); return; }
    if (toDate < fromDate) { setFormError("To date can't be before From date."); return; }
    if (duration === "half" && toDate !== fromDate) { setFormError("Half day only applies to a single date -- set To date the same as From date."); return; }
    if (!reason.trim()) { setFormError("Please enter a reason for leave."); return; }

    const err = await submit({
      leave_type: leaveType, from_date: fromDate, to_date: toDate, is_half_day: duration === "half", reason: reason.trim(),
    });
    if (err) setFormError(err);
    else resetForm();
  }

  const pendingCount = requests?.filter((r) => r.status === "pending").length ?? 0;

  return (
    <>
      <div className="mb-space-5">
        <h1 className="text-display">Holiday Application</h1>
        <p className="text-body">Manage your leave requests and view your leave balance.</p>
      </div>

      {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

      <div className="mb-space-5 grid grid-cols-1 gap-space-4 xs:grid-cols-2 lg:grid-cols-3">
        <InfoTile icon={CalendarDays} label="Leave balance" value={balance ? `${balance.remaining_days} left` : "—"} hint={balance ? `of ${balance.quota_days} days` : ""} />
        <InfoTile icon={Clock3} label="Used this year" value={balance ? `${balance.used_days}` : "—"} hint="days approved" />
        <InfoTile icon={CalendarIcon} label="Pending requests" value={String(pendingCount)} hint="awaiting approval" />
      </div>

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-5">
          <h3 className="text-label mb-space-4 font-bold text-ink-900">Apply for Leave</h3>

          <Field label="Leave type" htmlFor="leave_type" required>
            <select
              id="leave_type"
              value={leaveType}
              onChange={(e) => setLeaveType(e.target.value as LeaveType)}
              disabled={!canWrite}
              className="h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900 disabled:cursor-not-allowed disabled:bg-paper disabled:text-ink-400"
            >
              {LEAVE_TYPES.map((t) => (
                <option key={t} value={t}>{LEAVE_TYPE_LABELS[t]}</option>
              ))}
            </select>
          </Field>

          <div className="grid grid-cols-1 gap-x-space-4 sm:grid-cols-2">
            <Field label="From date" htmlFor="from_date" required>
              <Input id="from_date" type="date" value={fromDate} min={todayKey()} disabled={!canWrite} onChange={(e) => setFromDate(e.target.value)} />
            </Field>
            <Field label="To date" htmlFor="to_date" required>
              <Input id="to_date" type="date" value={toDate} min={fromDate || todayKey()} disabled={!canWrite} onChange={(e) => setToDate(e.target.value)} />
            </Field>
          </div>

          <Field label="Leave duration" required>
            <div className="flex items-center gap-space-4">
              {(["full", "half"] as const).map((d) => (
                <label key={d} className="flex items-center gap-space-2 text-[13.5px] text-ink-700">
                  <input type="radio" name="duration" checked={duration === d} disabled={!canWrite} onChange={() => setDuration(d)} className="h-4 w-4 accent-brand-600" />
                  {d === "full" ? "Full day" : "Half day"}
                </label>
              ))}
            </div>
          </Field>

          <Field label="Reason for leave" htmlFor="reason" required hint={`${reason.length}/${REASON_MAX}`}>
            <Textarea
              id="reason"
              rows={4}
              maxLength={REASON_MAX}
              placeholder="Enter reason for leave..."
              value={reason}
              disabled={!canWrite}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>

          {formError && <p className="mb-space-3 text-[12.5px] font-medium text-error">{formError}</p>}

          <div className="flex items-center gap-space-3">
            <Button variant="secondary" type="button" onClick={resetForm} disabled={submitting}>Cancel</Button>
            <Button type="button" onClick={handleSubmit} disabled={!canWrite || submitting}>
              <Send size={14} /> {submitting ? "Submitting…" : "Submit Application"}
            </Button>
          </div>
        </Card>

        <div className="space-y-space-4">
          <LeaveCalendar requests={requests || []} />
          <LeaveHistory requests={requests} />
        </div>
      </div>
    </>
  );
}

function InfoTile({ icon: Icon, label, value, hint }: { icon: typeof CalendarDays; label: string; value: string; hint?: string }) {
  return (
    <Card className="p-space-4">
      <div className="flex items-center gap-space-3">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
          <Icon size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="text-hint truncate">{label}</p>
          <p className="truncate text-[16px] font-bold text-ink-900">{value}</p>
          {hint && <p className="truncate text-[11px] text-ink-500">{hint}</p>}
        </div>
      </div>
    </Card>
  );
}

function LeaveCalendar({ requests }: { requests: LeaveRequestRow[] }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const statusByDate = useMemo(() => {
    const map = new Map<string, LeaveRequestStatus>();
    // Approved wins over pending/rejected if a date somehow has more than
    // one row touching it -- the most decided-and-real state is the most
    // useful one to show at a glance.
    const priority: Record<LeaveRequestStatus, number> = { approved: 3, pending: 2, rejected: 1 };
    for (const r of requests) {
      let d = new Date(`${r.from_date}T00:00:00`);
      const end = new Date(`${r.to_date}T00:00:00`);
      while (d <= end) {
        const key = dateKey(d);
        const existing = map.get(key);
        if (!existing || priority[r.status] > priority[existing]) map.set(key, r.status);
        d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1);
      }
    }
    return map;
  }, [requests]);

  const firstOfMonth = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const leadingBlanks = firstOfMonth.getDay();
  const monthLabel = firstOfMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const todayK = todayKey();

  function goToMonth(delta: number) {
    let m = month + delta, y = year;
    if (m > 12) { m = 1; y += 1; }
    if (m < 1) { m = 12; y -= 1; }
    setMonth(m); setYear(y);
  }

  const cells: { key: string | null; day: number | null }[] = [];
  for (let i = 0; i < leadingBlanks; i++) cells.push({ key: null, day: null });
  for (let d = 1; d <= daysInMonth; d++) cells.push({ key: `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`, day: d });

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label font-bold text-ink-900">Leave Calendar</h3>
        <div className="flex items-center gap-space-3 text-[11px] text-ink-500">
          <LegendDot tone="bg-success" label="Approved" />
          <LegendDot tone="bg-clay-500" label="Pending" />
          <LegendDot tone="bg-error" label="Rejected" />
        </div>
      </div>
      <div className="mb-space-3 flex items-center justify-center gap-space-3">
        <button type="button" onClick={() => goToMonth(-1)} className="flex h-7 w-7 items-center justify-center rounded-md text-ink-600 hover:bg-black/4"><ChevronLeft size={15} /></button>
        <span className="text-[13px] font-semibold text-ink-900">{monthLabel}</span>
        <button type="button" onClick={() => goToMonth(1)} className="flex h-7 w-7 items-center justify-center rounded-md text-ink-600 hover:bg-black/4"><ChevronRight size={15} /></button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-[10.5px] font-semibold text-ink-400">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((w) => <div key={w} className="py-1">{w}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((c, i) => {
          if (c.day === null) return <div key={`b${i}`} />;
          const status = statusByDate.get(c.key!);
          const isToday = c.key === todayK;
          return (
            <div
              key={c.key}
              className={cn(
                "flex aspect-square items-center justify-center rounded-md border text-[12px]",
                status === "approved" && "border-transparent bg-success-tint text-success",
                status === "pending" && "border-transparent bg-clay-100 text-clay-700",
                status === "rejected" && "border-transparent bg-error-tint text-error",
                !status && isToday && "border-brand-300 bg-brand-50 text-ink-900",
                !status && !isToday && "border-transparent text-ink-600",
              )}
            >
              {c.day}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function LegendDot({ tone, label }: { tone: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={cn("h-2 w-2 rounded-full", tone)} /> {label}
    </span>
  );
}

function LeaveHistory({ requests }: { requests: LeaveRequestRow[] | null }) {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 font-bold text-ink-900">Leave Request History</h3>
      {requests === null ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
      ) : requests.length === 0 ? (
        <p className="py-space-4 text-center text-[13px] text-ink-400">No leave requests yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="border-b border-line text-left text-label text-ink-400">
                <th className="py-space-2 pr-space-3 font-medium">Applied</th>
                <th className="py-space-2 pr-space-3 font-medium">Type</th>
                <th className="py-space-2 pr-space-3 font-medium">From</th>
                <th className="py-space-2 pr-space-3 font-medium">To</th>
                <th className="py-space-2 pr-space-3 font-medium">Days</th>
                <th className="py-space-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0">
                  <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{formatShort(r.submitted_at.slice(0, 10))}</td>
                  <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-900">{LEAVE_TYPE_LABELS[r.leave_type]}</td>
                  <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{formatShort(r.from_date)}</td>
                  <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{formatShort(r.to_date)}</td>
                  <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.is_half_day ? "Half" : r.duration_days}</td>
                  <td className="py-space-3">
                    <span className={cn("whitespace-nowrap rounded-full px-space-2 py-0.5 text-[11px] font-semibold", STATUS_STYLES[r.status])}>
                      {STATUS_LABELS[r.status]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
