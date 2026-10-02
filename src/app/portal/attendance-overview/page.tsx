"use client";

import { useMemo, useState } from "react";
import { CalendarCheck, Clock, MapPin, Search, UserRound, UserX } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import {
  useAttendanceOverview,
  type AttendanceOverviewRow,
  type AttendanceOverviewStatus,
} from "@/hooks/useAttendanceOverview";
import { checkInMethodLabel, checkInMethodStyle } from "@/lib/attendanceMethod";
import { formatHeaderDate, formatTimeOnly } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { cn } from "@/lib/cn";

// Collapses on_time/half_day into one "present" bucket for the filter --
// same grouping the stat tiles above already use -- so "Present" in the
// filter matches "Present" on the tile/badge, not the raw on_time status.
type AttendanceFilterStatus = "present" | "late" | "absent" | "leave" | "needs_review";

const FILTER_STATUS_OPTIONS: { value: AttendanceFilterStatus; label: string }[] = [
  { value: "present", label: "Present" },
  { value: "late", label: "Late" },
  { value: "absent", label: "Absent" },
  { value: "leave", label: "On leave" },
  { value: "needs_review", label: "Needs review" },
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
  const canOverride = usePermission("attendance_overview", "write");
  const {
    date,
    setDate,
    records,
    error,
    setStatus,
    overridingId,
    requests,
    reviewRequest,
    reviewingId,
  } = useAttendanceOverview(ready && canView);
  const [declineNotes, setDeclineNotes] = useState<Record<number, string>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const rows = useMemo(() => records || [], [records]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return rows.filter((r) => {
      if (statusFilter === "needs_review") {
        if (!r.check_in_needs_review) return false;
      } else if (statusFilter !== "all" && toFilterStatus(r.status) !== statusFilter) {
        return false;
      }
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
      <PageHeader title="Attendance Overview" description={formatHeaderDate(new Date())} />

      {!ready || !canView ? (
        !ready ? null : (
          <p className="text-ink-400 text-[13px]">
            You don&apos;t have access to Attendance Overview.
          </p>
        )
      ) : (
        <>
          {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

          <StatTileGrid cols={4} className="mb-space-4">
            <StatTile
              label="Present"
              value={records ? counts.present : null}
              icon={CalendarCheck}
            />
            <StatTile label="Late" value={records ? counts.late : null} icon={Clock} tint="clay" />
            <StatTile label="Absent" value={records ? counts.absent : null} icon={UserX} />
            <StatTile label="On leave" value={records ? counts.leave : null} icon={UserRound} />
          </StatTileGrid>

          {requests.length > 0 && (
            <Card className="p-space-4 mb-space-4 border-clay-300">
              <h3 className="text-label text-ink-900 font-bold">
                Check-in requests waiting for you ({requests.length})
              </h3>
              <p className="text-hint mt-space-1 mb-space-3">
                These staff couldn&apos;t check in the normal way and are asking you to approve it.
                Approving checks them in at the time they asked.
              </p>
              <ul className="space-y-space-3">
                {requests.map((q) => (
                  <li key={q.id} className="border-line p-space-3 rounded-md border">
                    <div className="gap-space-3 flex flex-wrap items-start justify-between">
                      <div className="min-w-0">
                        <p className="text-ink-900 text-[13px] font-bold">
                          {q.staff_name ?? "Staff member"}
                          {q.employee_id ? (
                            <span className="text-ink-400 font-medium"> · {q.employee_id}</span>
                          ) : null}
                        </p>
                        <p className="text-ink-400 text-[11.5px]">
                          Asked at {q.requested_at ? formatTimeOnly(q.requested_at) : "-"}
                        </p>
                        <p className="mt-space-1 text-ink-700 text-[12.5px]">
                          <span className="font-semibold">Reason:</span> {q.reason}
                        </p>
                        {q.failure_reason && (
                          <p className="mt-space-1 text-ink-500 text-[11.5px]">
                            Why the automatic check failed: {q.failure_reason}
                          </p>
                        )}
                        {q.latitude !== null && q.longitude !== null && (
                          <a
                            href={`https://www.google.com/maps?q=${q.latitude},${q.longitude}`}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-space-1 gap-space-1 text-brand-600 inline-flex items-center text-[12px] font-semibold hover:underline"
                          >
                            <MapPin size={12} /> See where they were
                            {q.accuracy_meters !== null
                              ? ` (location accurate to about ${Math.round(q.accuracy_meters)} m)`
                              : ""}
                          </a>
                        )}
                      </div>
                      {canOverride && (
                        <div className="gap-space-2 flex flex-wrap items-center">
                          <Input
                            type="text"
                            placeholder="Note if declining (optional)"
                            value={declineNotes[q.id] ?? ""}
                            onChange={(e) =>
                              setDeclineNotes((prev) => ({ ...prev, [q.id]: e.target.value }))
                            }
                            className="h-8 w-52 text-[12px]"
                          />
                          <button
                            type="button"
                            disabled={reviewingId === q.id}
                            onClick={() => reviewRequest(q, "reject", declineNotes[q.id])}
                            className="border-line text-ink-600 hover:bg-error-tint hover:text-error px-space-3 h-8 rounded-md border text-[12px] font-semibold disabled:opacity-40"
                          >
                            Decline
                          </button>
                          <button
                            type="button"
                            disabled={reviewingId === q.id}
                            onClick={() => reviewRequest(q, "approve")}
                            className="bg-brand-600 hover:bg-brand-700 px-space-3 h-8 rounded-md text-[12px] font-semibold text-white disabled:opacity-40"
                          >
                            Approve check-in
                          </button>
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">{dateLabel(date)}</h3>
                <p className="text-hint mt-space-1">
                  Hospital-wide attendance for the selected day.
                </p>
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
                {rows.length === 0
                  ? "No staff at this hospital yet."
                  : "No staff match your search/filters."}
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
                      <th className="py-space-2 pr-space-3 font-medium">Verified by</th>
                      <th className="py-space-2 font-medium">Status</th>
                      {canOverride && (
                        <th className="py-space-2 pl-space-3 font-medium">Actions</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((r: AttendanceOverviewRow) => (
                      <tr key={r.staff_id} className="border-line border-b last:border-0">
                        <td className="py-space-3 pr-space-3 text-ink-600 whitespace-nowrap">
                          {r.employee_id || "—"}
                        </td>
                        <td className="py-space-3 pr-space-3 text-ink-900 font-semibold whitespace-nowrap">
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
                        <td className="py-space-3 pr-space-3 whitespace-nowrap">
                          {r.check_in_verified_method ? (
                            <span className="gap-space-1 inline-flex items-center">
                              <span
                                className={cn(
                                  "px-space-2 rounded-full py-0.5 text-[11px] font-semibold",
                                  checkInMethodStyle(r.check_in_verified_method),
                                )}
                              >
                                {checkInMethodLabel(r.check_in_verified_method)}
                              </span>
                              {r.check_in_needs_review && (
                                <span
                                  title="The hospital WiFi check is on, but this person was matched by location only."
                                  className="bg-clay-100 text-clay-700 px-space-2 rounded-full py-0.5 text-[11px] font-semibold"
                                >
                                  Review
                                </span>
                              )}
                            </span>
                          ) : (
                            "-"
                          )}
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
                        {canOverride && (
                          <td className="py-space-3 pl-space-3 whitespace-nowrap">
                            <div className="gap-space-2 flex items-center">
                              <button
                                type="button"
                                disabled={overridingId === r.staff_id || r.status === "on_time"}
                                onClick={() => setStatus(r, "on_time")}
                                className="border-line text-ink-600 hover:bg-success-tint hover:text-success px-space-2 h-7 rounded-md border text-[11.5px] font-semibold disabled:cursor-not-allowed disabled:opacity-40"
                              >
                                Mark Present
                              </button>
                              <button
                                type="button"
                                disabled={overridingId === r.staff_id || r.status === "absent"}
                                onClick={() => setStatus(r, "absent")}
                                className="border-line text-ink-600 hover:bg-error-tint hover:text-error px-space-2 h-7 rounded-md border text-[11.5px] font-semibold disabled:cursor-not-allowed disabled:opacity-40"
                              >
                                Mark Absent
                              </button>
                            </div>
                          </td>
                        )}
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
