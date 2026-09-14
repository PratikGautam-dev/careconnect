"use client";

import { useMemo, useState } from "react";
import { BarChart3, CalendarDays, Clock, Download, UserX } from "lucide-react";
import { Bar, BarChart, Cell, LabelList, Pie, PieChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatHeaderDateDayMonth } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/cn";
import {
  MONTH_OPTIONS,
  STATUS_COLORS,
  STATUS_FILTER_OPTIONS,
  STATUS_LABELS,
  STATUS_STYLES,
  initialAttendanceRecords,
  initialAttendanceStats,
  initialAttendanceStatusBreakdown,
  initialWeeklyTrend,
  type AttendanceStatus,
} from "./attendance-mock";

/** /portal/attendance -- a personal attendance summary (stat tiles, this
 * month's trend, a status breakdown donut, and a day-by-day record table),
 * built from the reference screenshot. Entirely frontend-mock for now
 * (explicit instruction): Check-in/Check-out has no page of its own yet,
 * and once it does, THIS page's Present/Absent/Late numbers and the
 * records table below become real, derived from actual check-in/check-out
 * rows -- only "Leave" is ever expected to read from something real sooner
 * (the existing Leave Requests/Holiday Application data), everything else
 * here waits on that follow-up build. Month/Status are real client-side
 * filters over the mock records array, not wired to a backend query.
 *
 * Gated by the real "attendance" page_key (migration 20260914130000) --
 * view+write for every role except the seeded Admin role by default,
 * editable per-hospital via Settings -> Roles & Permissions like any other
 * page. */
export default function AttendancePage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("attendance", "view");
  const stats = initialAttendanceStats();
  const trend = initialWeeklyTrend();
  const breakdown = initialAttendanceStatusBreakdown();
  const totalDays = breakdown.reduce((sum, s) => sum + s.count, 0);
  const [month, setMonth] = useState(MONTH_OPTIONS[0]);
  const [statusFilter, setStatusFilter] = useState<AttendanceStatus | "all">("all");

  const records = useMemo(() => {
    const all = initialAttendanceRecords();
    return statusFilter === "all" ? all : all.filter((r) => r.status === statusFilter);
  }, [statusFilter]);

  if (!ready) return null;

  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="attendance">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Attendance.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="attendance">
      <PageHeader
        title="Attendance"
        description={formatHeaderDateDayMonth(new Date())}
        actions={
          <Button
            variant="secondary"
            onClick={() => toast.success("Report download isn't wired up yet", "Coming soon, once real attendance data is available.")}
          >
            <Download size={16} /> Download Report
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-space-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={CalendarDays} tint="brand" label="Present days" value={stats.presentDays} />
        <StatCard icon={UserX} tint="error" label="Absent days" value={stats.absentDays} />
        <StatCard icon={Clock} tint="clay" label="Late check-ins" value={stats.lateCheckIns} />
        <StatCard icon={BarChart3} tint="success" label="Overtime hours" value={stats.overtimeHours} />
      </div>

      <div className="mt-space-4 grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 font-bold text-ink-900">Attendance trend (this month)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={trend} margin={{ top: 20, right: 8, bottom: 0, left: -16 }}>
              <XAxis
                dataKey="week"
                tickLine={false}
                axisLine={{ stroke: "#c3c2b7" }}
                tick={{ fontSize: 12, fill: "#898781" }}
              />
              <YAxis
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: "#898781" }}
              />
              <Bar dataKey="percent" radius={[4, 4, 0, 0]} maxBarSize={64}>
                <LabelList dataKey="percent" position="top" formatter={(v: number) => `${v}%`} style={{ fontSize: 12, fontWeight: 700, fill: "#26251f" }} />
                {trend.map((point, i) => (
                  <Cell key={point.week} fill={i === trend.length - 1 ? "#00949E" : "#bfe3e6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 font-bold text-ink-900">Attendance status</h3>
          <div className="flex items-center gap-space-4">
            <div className="relative w-[55%] shrink-0">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={breakdown}
                    dataKey="count"
                    nameKey="label"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={2}
                    strokeWidth={0}
                  >
                    {breakdown.map((slice) => (
                      <Cell key={slice.status} fill={STATUS_COLORS[slice.status]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[22px] font-bold leading-none text-ink-900">{totalDays}</span>
                <span className="text-[11px] text-ink-400">Total days</span>
              </div>
            </div>
            <ul className="flex-1 space-y-space-2">
              {breakdown.map((slice) => (
                <li key={slice.status} className="flex items-center gap-space-2 text-[12.5px]">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: STATUS_COLORS[slice.status] }} />
                  <span className="flex-1 text-ink-900">{slice.label}</span>
                  <span className="w-6 text-right font-semibold text-ink-900">{slice.count}</span>
                  <span className="w-10 text-right text-ink-400">{Math.round((slice.count / totalDays) * 100)}%</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>

      <Card className="mt-space-4 p-space-4">
        <div className="mb-space-3 flex flex-wrap items-center justify-between gap-space-3">
          <h3 className="text-label font-bold text-ink-900">Attendance records</h3>
          <div className="flex flex-wrap items-center gap-space-3">
            <label className="flex items-center gap-space-2 text-[12.5px] text-ink-600">
              Month
              <select
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className="h-9 rounded-md border border-line bg-card px-space-2 text-[12.5px] text-ink-900"
              >
                {MONTH_OPTIONS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-space-2 text-[12.5px] text-ink-600">
              Status
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as AttendanceStatus | "all")}
                className="h-9 rounded-md border border-line bg-card px-space-2 text-[12.5px] text-ink-900"
              >
                {STATUS_FILTER_OPTIONS.map((s) => (
                  <option key={s} value={s}>{s === "all" ? "All" : STATUS_LABELS[s]}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {records.length === 0 ? (
          <p className="py-space-4 text-center text-[13px] text-ink-400">No attendance records for this filter.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-line text-left text-label text-ink-400">
                  <th className="py-space-2 pr-space-3 font-medium">Date</th>
                  <th className="py-space-2 pr-space-3 font-medium">Check-in</th>
                  <th className="py-space-2 pr-space-3 font-medium">Check-out</th>
                  <th className="py-space-2 pr-space-3 font-medium">Break</th>
                  <th className="py-space-2 pr-space-3 font-medium">Working hours</th>
                  <th className="py-space-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.date} className="border-b border-line last:border-0">
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-900">{r.date}</td>
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.checkIn ?? "-"}</td>
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.checkOut ?? "-"}</td>
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.breakTime ?? "-"}</td>
                    <td className="py-space-3 pr-space-3 whitespace-nowrap text-ink-600">{r.workingHours ?? "-"}</td>
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
    </PortalShell>
  );
}

function StatCard({
  icon: Icon, tint, label, value,
}: {
  icon: typeof CalendarDays; tint: "brand" | "error" | "clay" | "success"; label: string; value: number | string;
}) {
  const tintClasses: Record<string, string> = {
    brand: "bg-brand-50 text-brand-600",
    error: "bg-error-tint text-error",
    clay: "bg-clay-100 text-clay-700",
    success: "bg-success-tint text-success",
  };
  return (
    <Card className="p-space-4">
      <div className="flex items-center gap-space-3">
        <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-full", tintClasses[tint])}>
          <Icon size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="text-label truncate font-medium text-ink-600">{label}</p>
          <p className="text-[22px] font-bold leading-tight text-ink-900">{value}</p>
        </div>
      </div>
    </Card>
  );
}
