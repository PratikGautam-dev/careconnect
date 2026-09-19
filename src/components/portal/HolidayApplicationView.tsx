"use client";

import { useMemo, useState } from "react";
import {
  Calendar as CalendarIcon,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Send,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { useHolidayApplication } from "@/hooks/useHolidayApplication";
import { formatLeaveTypeLabel, type LeaveRequestRow, type LeaveRequestStatus, type LeaveType } from "@/hooks/useLeaveRequests";
import { cn } from "@/lib/cn";

const STATUS_STYLES: Record<LeaveRequestStatus, string> = {
  pending: "bg-clay-100 text-clay-700",
  approved: "bg-success-tint text-success",
  rejected: "bg-error-tint text-error",
};
const STATUS_LABELS: Record<LeaveRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

const REASON_MAX = 500;

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function formatShort(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Doctor/staff self-service leave application -- submits into the same
 * leave_requests table the admin Leave Requests page reviews, so a
 * submission here shows up there immediately, pending approval. Any
 * signed-in staff member with the "holiday_application" permission can
 * use this. Self-fetches /api/portal/leave-requests/mine; the caller owns
 * auth/guard/shell. */
export function HolidayApplicationView({ canWrite }: { canWrite: boolean }) {
  const { requests, balance, leaveTypes, error, submitting, submit } = useHolidayApplication(true);

  const [leaveType, setLeaveType] = useState<LeaveType>("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [duration, setDuration] = useState<"full" | "half">("full");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // leaveTypes only arrives after the initial /mine fetch resolves -- a
  // derived fallback rather than syncing it into state via an effect
  // (avoids a spurious extra render once the fetch lands): once the caller
  // picks something explicitly, that choice wins.
  const selectedLeaveType = leaveType || leaveTypes[0] || "";

  function resetForm() {
    setLeaveType("");
    setFromDate("");
    setToDate("");
    setDuration("full");
    setReason("");
    setFormError(null);
  }

  async function handleSubmit() {
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
    if (duration === "half" && toDate !== fromDate) {
      setFormError("Half day only applies to a single date -- set To date the same as From date.");
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
      is_half_day: duration === "half",
      reason: reason.trim(),
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

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <div className="mb-space-5 gap-space-4 xs:grid-cols-2 grid grid-cols-1 lg:grid-cols-3">
        <InfoTile
          icon={CalendarDays}
          label="Leave balance"
          value={balance ? `${balance.remaining_days} left` : "—"}
          hint={balance ? `of ${balance.quota_days} days` : ""}
        />
        <InfoTile
          icon={Clock3}
          label="Used this year"
          value={balance ? `${balance.used_days}` : "—"}
          hint="days approved"
        />
        <InfoTile
          icon={CalendarIcon}
          label="Pending requests"
          value={String(pendingCount)}
          hint="awaiting approval"
        />
      </div>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-2">
        <Card className="p-space-5">
          <h3 className="text-label mb-space-4 text-ink-900 font-bold">Apply for Leave</h3>

          <Field label="Leave type" htmlFor="leave_type" required>
            <select
              id="leave_type"
              value={selectedLeaveType}
              onChange={(e) => setLeaveType(e.target.value as LeaveType)}
              disabled={!canWrite || leaveTypes.length === 0}
              className="border-line bg-card px-space-3 text-ink-900 disabled:bg-paper disabled:text-ink-400 h-11 w-full rounded-md border text-[14px] disabled:cursor-not-allowed"
            >
              {leaveTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>

          <div className="gap-x-space-4 grid grid-cols-1 sm:grid-cols-2">
            <Field label="From date" htmlFor="from_date" required>
              <Input
                id="from_date"
                type="date"
                value={fromDate}
                min={todayKey()}
                disabled={!canWrite}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </Field>
            <Field label="To date" htmlFor="to_date" required>
              <Input
                id="to_date"
                type="date"
                value={toDate}
                min={fromDate || todayKey()}
                disabled={!canWrite}
                onChange={(e) => setToDate(e.target.value)}
              />
            </Field>
          </div>

          <Field label="Leave duration" required>
            <div className="gap-space-4 flex items-center">
              {(["full", "half"] as const).map((d) => (
                <label key={d} className="gap-space-2 text-ink-700 flex items-center text-[13.5px]">
                  <input
                    type="radio"
                    name="duration"
                    checked={duration === d}
                    disabled={!canWrite}
                    onChange={() => setDuration(d)}
                    className="accent-brand-600 h-4 w-4"
                  />
                  {d === "full" ? "Full day" : "Half day"}
                </label>
              ))}
            </div>
          </Field>

          <Field
            label="Reason for leave"
            htmlFor="reason"
            required
            hint={`${reason.length}/${REASON_MAX}`}
          >
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

          {formError && (
            <p className="mb-space-3 text-error text-[12.5px] font-medium">{formError}</p>
          )}

          <div className="gap-space-3 flex items-center">
            <Button variant="secondary" type="button" onClick={resetForm} disabled={submitting}>
              Cancel
            </Button>
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

function InfoTile({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof CalendarDays;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card className="p-space-4">
      <div className="gap-space-3 flex items-center">
        <span className="bg-brand-50 text-brand-600 flex h-12 w-12 shrink-0 items-center justify-center rounded-full">
          <Icon size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="text-hint truncate">{label}</p>
          <p className="text-ink-900 truncate text-[16px] font-bold">{value}</p>
          {hint && <p className="text-ink-500 truncate text-[11px]">{hint}</p>}
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
    let m = month + delta,
      y = year;
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

  const cells: { key: string | null; day: number | null }[] = [];
  for (let i = 0; i < leadingBlanks; i++) cells.push({ key: null, day: null });
  for (let d = 1; d <= daysInMonth; d++)
    cells.push({
      key: `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
      day: d,
    });

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Leave Calendar</h3>
        <div className="gap-space-3 text-ink-500 flex items-center text-[11px]">
          <LegendDot tone="bg-success" label="Approved" />
          <LegendDot tone="bg-clay-500" label="Pending" />
          <LegendDot tone="bg-error" label="Rejected" />
        </div>
      </div>
      <div className="mb-space-3 gap-space-3 flex items-center justify-center">
        <button
          type="button"
          onClick={() => goToMonth(-1)}
          className="text-ink-600 flex h-7 w-7 items-center justify-center rounded-md hover:bg-black/4"
        >
          <ChevronLeft size={15} />
        </button>
        <span className="text-ink-900 text-[13px] font-semibold">{monthLabel}</span>
        <button
          type="button"
          onClick={() => goToMonth(1)}
          className="text-ink-600 flex h-7 w-7 items-center justify-center rounded-md hover:bg-black/4"
        >
          <ChevronRight size={15} />
        </button>
      </div>
      <div className="text-ink-400 grid grid-cols-7 gap-1 text-center text-[10.5px] font-semibold">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((w) => (
          <div key={w} className="py-1">
            {w}
          </div>
        ))}
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
                status === "approved" && "bg-success-tint text-success border-transparent",
                status === "pending" && "bg-clay-100 text-clay-700 border-transparent",
                status === "rejected" && "bg-error-tint text-error border-transparent",
                !status && isToday && "border-brand-300 bg-brand-50 text-ink-900",
                !status && !isToday && "text-ink-600 border-transparent",
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
      <h3 className="text-label mb-space-3 text-ink-900 font-bold">Leave Request History</h3>
      {requests === null ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
      ) : requests.length === 0 ? (
        <p className="py-space-4 text-ink-400 text-center text-[13px]">No leave requests yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="border-line text-label text-ink-400 border-b text-left">
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
                <tr key={r.id} className="border-line border-b last:border-0">
                  <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                    {formatShort(r.submitted_at.slice(0, 10))}
                  </td>
                  <td className="py-space-3 pr-space-3 text-ink-900 whitespace-nowrap">
                    {formatLeaveTypeLabel(r.leave_type)}
                  </td>
                  <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                    {formatShort(r.from_date)}
                  </td>
                  <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                    {formatShort(r.to_date)}
                  </td>
                  <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                    {r.is_half_day ? "Half" : r.duration_days}
                  </td>
                  <td className="py-space-3">
                    <span
                      className={cn(
                        "px-space-2 rounded-full py-0.5 text-[11px] font-semibold whitespace-nowrap",
                        STATUS_STYLES[r.status],
                      )}
                    >
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
