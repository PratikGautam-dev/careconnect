"use client";

import { useMemo, useState } from "react";
import { CalendarCheck, Clock, Search, UserRound, UserX } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { PortalTopBarActions } from "@/components/portal/PortalTopBarActions";
import { StatTile } from "@/components/portal/StatTile";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import {
  useAttendanceOverview,
  type AttendanceOverviewRow,
  type AttendanceOverviewStatus,
} from "@/hooks/useAttendanceOverview";
import { formatHeaderDate, formatTimeOnly } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { cn } from "@/lib/cn";

// Collapses on_time/half_day into one "present" bucket for the filter --
// same grouping the stat tiles above already use -- so "Present" in the
// filter matches "Present" on the tile/badge, not the raw on_time status.
type AttendanceFilterStatus = "present" | "late" | "absent" | "leave";

const FILTER_STATUS_OPTIONS: { value: AttendanceFilterStatus; label: string }[] = [
  { value: "present", label: "Present" },
  { value: "late", label: "Late" },
  { value: "absent", label: "Absent" },
  { value: "leave", label: "On leave" },
];

function toFilterStatus(status: AttendanceOverviewStatus): AttendanceFilterStatus {
  return status === "on_time" || status === "half_day" ? "present" : status;
}

const STATUS_LABELS: Record<AttendanceOverviewStatus, string> = {
  on_time: "Present",
  half_day: "Present",
  late: "Late",
  leave: "On leave",
  absent: "Absent",
};

const STATUS_STYLES: Record<AttendanceOverviewStatus, string> = {
  on_time: "bg-success-tint text-success",
  half_day: "bg-success-tint text-success",
  late: "bg-clay-100 text-clay-700",
  leave: "bg-brand-50 text-brand-600",
  absent: "bg-error-tint text-error",
};

function formatMinutes(minutes: number): string {
  if (!minutes) return "-";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
}

function dateLabel(dateKey: string): string {
  return new Date(`${dateKey}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "long",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Admin-facing hospital-wide attendance roster for ONE selected day
 * (default today) -- every staff member, not just whoever happened to
 * check in (db.get_hospital_attendance() left-joins the full staff list,
 * so a no-show shows up as "Absent" rather than being omitted). A flat
 * table, one row per staff member for the selected date, is the more
 * useful default here than a master-detail "pick one person" layout
 * (Leave Requests' own pattern) -- the question an admin actually opens
 * this page to answer is "who's here/late/absent TODAY", not one person's
 * history. One person's full attendance history (StaffAttendanceHistoryDialog)
 * lives as a quick action on that staff/doctor's own detail panel instead
 * (Settings -> Staff / Doctors pages), not a click-through from this
 * table -- confirmed with the user. Gated by "attendance_overview" --
 * admin-only by default, separate from "attendance" (personal history,
 * off for admin) and "attendance_settings" (geofence/shift config). */
export default function AttendanceOverviewPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("attendance_overview", "view");
  const { date, setDate, records, error } = useAttendanceOverview(ready && canView);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const rows = useMemo(() => records || [], [records]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return rows.filter((r) => {
      if (statusFilter !== "all" && toFilterStatus(r.status) !== statusFilter) return false;
      if (!q) return true;
      return (
        r.staff_name.toLowerCase().includes(q) ||
        (r.employee_id || "").toLowerCase().includes(q) ||
        (r.department_name || "").toLowerCase().includes(q)
      );
    });
  }, [rows, searchQuery, statusFilter]);

  const counts = useMemo(() => {
    const c = { present: 0, late: 0, absent: 0, leave: 0 };
    for (const r of rows) {
      if (r.status === "on_time" || r.status === "half_day") c.present += 1;
      else if (r.status === "late") c.late += 1;
      else if (r.status === "absent") c.absent += 1;
      else if (r.status === "leave") c.leave += 1;
    }
    return c;
  }, [rows]);

  return (
    <PortalShell hospital={hospital} active="attendance-overview">
      <PageHeader
        title="Attendance Overview"
        description={formatHeaderDate(new Date())}
        actions={<PortalTopBarActions />}
      />

      {!ready || !canView ? (
        !ready ? null : (
          <p className="text-ink-400 text-[13px]">You don&apos;t have access to Attendance Overview.</p>
        )
      ) : (
        <>
          {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

          <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Present"
              value={records ? counts.present : null}
              deltaPct={null}
              hint={dateLabel(date)}
              icon={CalendarCheck}
            />
            <StatTile
              label="Late"
              value={records ? counts.late : null}
              deltaPct={null}
              hint={dateLabel(date)}
              icon={Clock}
              tint="clay"
            />
            <StatTile
              label="Absent"
              value={records ? counts.absent : null}
              deltaPct={null}
              hint={dateLabel(date)}
              icon={UserX}
            />
            <StatTile
              label="On leave"
              value={records ? counts.leave : null}
              deltaPct={null}
              hint={dateLabel(date)}
              icon={UserRound}
            />
          </div>

          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">{dateLabel(date)}</h3>
                <p className="text-hint mt-space-1">Hospital-wide attendance for the selected day.</p>
              </div>
              <Input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="h-9 w-auto"
              />
            </div>

            <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
              <div className="relative min-w-50 flex-1">
                <Search
                  size={14}
                  className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
                />
                <input
                  type="text"
                  placeholder="Search by name, employee ID or department…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                />
              </div>
              <FilterSelect
                value={statusFilter}
                onChange={setStatusFilter}
                allLabel="All Status"
                options={FILTER_STATUS_OPTIONS}
              />
            </div>

            {records === null ? (
              <p className="py-space-4 text-ink-400 text-center text-[13px]">Loading…</p>
            ) : filteredRows.length === 0 ? (
              <p className="py-space-4 text-ink-400 text-center text-[13px]">
                {rows.length === 0 ? "No staff at this hospital yet." : "No staff match your search/filters."}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12.5px]">
                  <thead>
                    <tr className="border-line text-label text-ink-400 border-b text-left">
                      <th className="py-space-2 pr-space-3 font-medium">Employee ID</th>
                      <th className="py-space-2 pr-space-3 font-medium">Staff</th>
                      <th className="py-space-2 pr-space-3 font-medium">Role</th>
                      <th className="py-space-2 pr-space-3 font-medium">Department</th>
                      <th className="py-space-2 pr-space-3 font-medium">Check-in</th>
                      <th className="py-space-2 pr-space-3 font-medium">Check-out</th>
                      <th className="py-space-2 pr-space-3 font-medium">Working hours</th>
                      <th className="py-space-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((r: AttendanceOverviewRow) => (
                      <tr key={r.staff_id} className="border-line border-b last:border-0">
                        <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                          {r.employee_id || "—"}
                        </td>
                        <td className="py-space-3 pr-space-3 text-ink-900 whitespace-nowrap font-semibold">
                          {r.staff_name}
                        </td>
                        <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                          {r.role_name}
                        </td>
                        <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                          {r.department_name || "—"}
                        </td>
                        <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                          {r.check_in_at ? formatTimeOnly(r.check_in_at) : "-"}
                        </td>
                        <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                          {r.check_out_at ? formatTimeOnly(r.check_out_at) : "-"}
                        </td>
                        <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                          {formatMinutes(r.working_minutes)}
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
        </>
      )}
    </PortalShell>
  );
}
