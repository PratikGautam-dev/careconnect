"use client";

import { DepartmentDonut } from "@/components/portal/DepartmentDonut";
import { DoctorDashboardView } from "@/components/portal/DoctorDashboardView";
import { PortalShell } from "@/components/portal/PortalShell";
import { RecentAppointmentsTable } from "@/components/portal/RecentAppointmentsTable";
import { StatTile } from "@/components/portal/StatTile";
import { WeeklyTrendChart } from "@/components/portal/WeeklyTrendChart";
import { usePortalDashboard } from "@/hooks/usePortalDashboard";
import { useStaffSession } from "@/lib/staffAuth";

const TIER_LABELS: Record<string, string> = { tier1: "Tier 1", tier2: "Tier 2", tier3: "Tier 3" };

export default function PortalDashboardPage() {
  // Doctors get their own dashboard content (today's appointments, their own
  // stats) instead of the hospital-wide widgets below -- same shared
  // PortalShell/nav either way, per the RBAC-driven consolidation.
  //
  // useStaffSession (not getStaffSession directly): null on the server AND
  // on the client's own first render, so both agree on rendering
  // HospitalDashboard first -- getStaffSession() itself returns the real
  // session immediately client-side, which for a doctor account used to
  // swap in an entirely different component tree (DoctorDashboardView) on
  // the very first client render than what the server had sent, a much
  // bigger hydration mismatch than a mismatched text node. The real
  // session (and DoctorDashboardView, if applicable) arrives an instant
  // later as a normal client-only update.
  const session = useStaffSession();
  if (session?.role === "doctor") {
    return (
      <PortalShell hospital={session.hospital} active="dashboard">
        <DoctorDashboardView />
      </PortalShell>
    );
  }

  return <HospitalDashboard />;
}

function HospitalDashboard() {
  const { data, error, hospital } = usePortalDashboard();

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper px-space-4">
        <p className="text-[14px] text-error">{error}</p>
      </div>
    );
  }

  return (
    <PortalShell hospital={hospital} active="dashboard">
        <div className="mb-space-5 flex flex-wrap items-center justify-between gap-space-3">
          <div>
            <h1 className="text-display">
              Hospital Admin Dashboard
              {data && (
                <span className="ml-space-2 text-[15px] font-medium text-ink-400">
                  ({TIER_LABELS[data.hospital.data_tier] || data.hospital.data_tier})
                </span>
              )}
            </h1>
          </div>
          <div className="flex gap-space-2">
            <select
              disabled
              title="Coming soon"
              className="h-9 cursor-not-allowed rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-600"
            >
              <option>Today</option>
            </select>
          </div>
        </div>

        {!data ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <>
            <div className="mb-space-4 grid grid-cols-1 gap-space-4 md:grid-cols-2 lg:grid-cols-5">
              <StatTile label="Upcoming appointments" value={data.stats.upcoming_appointments} deltaPct={null} hint="Currently booked" />
              <StatTile label="Today's appointments" value={data.stats.today_appointments} deltaPct={data.stats.today_appointments_delta_pct} />
              <StatTile label="Confirmed" value={data.stats.confirmed_today} deltaPct={data.stats.confirmed_today_delta_pct} />
              <StatTile label="New patients" value={data.stats.new_patients_today} deltaPct={data.stats.new_patients_today_delta_pct} />
              <StatTile label="No-shows" value={data.stats.no_shows_today} deltaPct={data.stats.no_shows_today_delta_pct} upIsGood={false} />
            </div>

            <div className="mb-space-4 grid grid-cols-1 gap-space-4 lg:grid-cols-2">
              <WeeklyTrendChart data={data.weekly_counts} />
              <DepartmentDonut data={data.department_breakdown} />
            </div>

            <div className="mb-space-4">
              <RecentAppointmentsTable appointments={data.recent_appointments} />
            </div>
          </>
        )}
    </PortalShell>
  );
}
