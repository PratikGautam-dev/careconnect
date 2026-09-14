"use client";

import { BarChart3, Briefcase, Clock, Coffee, LogIn, LogOut, Play, User } from "lucide-react";
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
  HISTORY_STATUS_LABELS,
  HISTORY_STATUS_STYLES,
  MOCK_TODAY_SUMMARY,
  initialCheckInHistory,
  initialTodaysActivity,
  type ActivityEventKind,
} from "./check-in-out-mock";

const ACTIVITY_ICONS: Record<ActivityEventKind, typeof LogIn> = {
  check_in: LogIn,
  break_start: Coffee,
  break_end: Play,
  current_session: Briefcase,
};

function notWiredYet() {
  toast.success("This action isn't wired up yet", "Coming soon, once real check-in/check-out tracking is available.");
}

/** /portal/check-in-out -- today's check-in/check-out activity, a live
 * working-hours ring, quick-action buttons, and recent history. Entirely
 * frontend-mock for now (explicit instruction, same as the Attendance
 * page's own follow-up note): Check In/Start Break/End Break/Check Out and
 * "Mark Attendance" don't call anything real yet, and none of the times/
 * hours below are live -- this is a visual pass matching the reference
 * screenshot, with the real wiring (and, through it, Attendance's own
 * Present/Absent/Late numbers) a deliberate later build.
 *
 * Gated by the real "check_in_out" page_key (migration 20260914130000) --
 * view+write for every role except the seeded Admin role by default,
 * editable per-hospital via Settings -> Roles & Permissions like any other
 * page. */
export default function CheckInOutPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("check_in_out", "view");
  const activity = initialTodaysActivity();
  const history = initialCheckInHistory();
  const s = MOCK_TODAY_SUMMARY;
  const ringPercent = Math.min(100, Math.round((s.workingMinutes / s.referenceDayMinutes) * 100));

  if (!ready) return null;

  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="check-in-out">
        <p className="text-[13px] text-ink-400">You don&apos;t have access to Check-in / Check-out.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="check-in-out">
      <PageHeader
        title="Check-in / Check-out"
        description={formatHeaderDateDayMonth(new Date())}
        actions={
          <Button onClick={notWiredYet}>
            <Clock size={16} /> Mark Attendance
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-space-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-space-4">
          <div className="flex items-center gap-space-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <User size={20} strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <p className="text-label truncate font-medium text-ink-600">Current status</p>
              <p className="text-[22px] font-bold leading-tight text-success">{s.currentStatus}</p>
              <p className="mt-space-0.5 flex items-center gap-space-1 text-[11.5px] text-ink-400">
                <span className="h-1.5 w-1.5 rounded-full bg-success" /> Since {s.checkedInSince}
              </p>
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
              <p className="text-[22px] font-bold leading-tight text-ink-900">{s.checkInTime}</p>
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
              <p className="text-[22px] font-bold leading-tight text-ink-900">{s.breakTaken}</p>
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
              <p className="text-[22px] font-bold leading-tight text-ink-900">{s.workingHours}</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-space-4 grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <h3 className="text-label mb-space-4 font-bold text-ink-900">Today&apos;s activity</h3>
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
        </Card>

        <Card className="p-space-4">
          <div className="mb-space-4 flex items-center justify-between">
            <h3 className="text-label font-bold text-ink-900">Live work timer</h3>
            <span className="flex items-center gap-space-1 text-[12px] font-semibold text-success">
              <span className="h-1.5 w-1.5 rounded-full bg-success" /> Currently working
            </span>
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
                <span className="text-[24px] font-bold leading-none text-ink-900">{s.workingHours}</span>
                <span className="mt-space-1 text-[11.5px] text-ink-400">Working today</span>
              </div>
            </div>
            <div className="flex-1 space-y-space-2">
              <div className="flex items-center gap-space-3 rounded-md bg-paper p-space-3">
                <LogIn size={16} strokeWidth={2} className="shrink-0 text-ink-400" />
                <div>
                  <p className="text-[11.5px] text-ink-400">Check-in time</p>
                  <p className="text-[13px] font-bold text-ink-900">{s.checkInTime}</p>
                </div>
              </div>
              <div className="flex items-center gap-space-3 rounded-md bg-paper p-space-3">
                <Coffee size={16} strokeWidth={2} className="shrink-0 text-ink-400" />
                <div>
                  <p className="text-[11.5px] text-ink-400">Break taken</p>
                  <p className="text-[13px] font-bold text-ink-900">{s.breakTaken}</p>
                </div>
              </div>
              <div className="flex items-center gap-space-3 rounded-md bg-paper p-space-3">
                <Clock size={16} strokeWidth={2} className="shrink-0 text-ink-400" />
                <div>
                  <p className="text-[11.5px] text-ink-400">Active since</p>
                  <p className="text-[13px] font-bold text-ink-900">{s.activeSince}</p>
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
              onClick={notWiredYet}
              className="flex flex-col items-center gap-space-2 rounded-md bg-brand-600 py-space-4 text-white shadow-[var(--shadow-sm)] transition-colors duration-150 hover:bg-brand-700"
            >
              <LogIn size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Check In</span>
            </button>
            <button
              type="button"
              onClick={notWiredYet}
              className="flex flex-col items-center gap-space-2 rounded-md border border-line bg-card py-space-4 text-ink-900 transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50"
            >
              <Coffee size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Start Break</span>
            </button>
            <button
              type="button"
              onClick={notWiredYet}
              className="flex flex-col items-center gap-space-2 rounded-md border border-line bg-card py-space-4 text-ink-900 transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50"
            >
              <Play size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">End Break</span>
            </button>
            <button
              type="button"
              onClick={notWiredYet}
              className="flex flex-col items-center gap-space-2 rounded-md border border-line bg-card py-space-4 text-ink-900 transition-colors duration-150 hover:border-brand-300 hover:bg-brand-50"
            >
              <LogOut size={20} strokeWidth={2} />
              <span className="text-[13px] font-semibold">Check Out</span>
            </button>
          </div>
          <p className="mt-space-3 flex items-center gap-space-1.5 text-[12px] text-ink-400">
            <span className="h-1.5 w-1.5 rounded-full bg-success" /> {s.currentStatus}
          </p>
        </Card>

        <Card className="p-space-4">
          <div className="mb-space-3 flex items-center justify-between">
            <h3 className="text-label font-bold text-ink-900">Recent check-in history</h3>
            <button type="button" onClick={notWiredYet} className="text-[12.5px] font-semibold text-brand-600 hover:underline">
              View all
            </button>
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
                {history.map((r) => (
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
    </PortalShell>
  );
}
