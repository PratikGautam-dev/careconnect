"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ActivityFeed } from "@/components/portal/ActivityFeed";
import { DepartmentDonut } from "@/components/portal/DepartmentDonut";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
import { RecentAppointmentsTable } from "@/components/portal/RecentAppointmentsTable";
import { StatTile } from "@/components/portal/StatTile";
import { WeeklyTrendChart } from "@/components/portal/WeeklyTrendChart";
import { getPortalHospital, portalFetch, type PortalHospital } from "@/lib/portalAuth";

type DashboardData = {
  hospital: PortalHospital;
  stats: {
    today_appointments: number;
    today_appointments_delta_pct: number | null;
    confirmed_today: number;
    confirmed_today_delta_pct: number | null;
    new_patients_today: number;
    new_patients_today_delta_pct: number | null;
    no_shows_today: number;
    no_shows_today_delta_pct: number | null;
  };
  weekly_counts: { date: string; label: string; count: number }[];
  department_breakdown: { department_name: string; count: number }[];
  recent_appointments: {
    id: number;
    phone: string;
    department_name: string;
    doctor_name: string;
    scheduled_at: string;
    status: string;
    source: string;
  }[];
  activity_feed: { label: string; phone: string; doctor_name: string; department_name: string; at: string }[];
};

const TIER_LABELS: Record<string, string> = { tier1: "Tier 1", tier2: "Tier 2", tier3: "Tier 3" };

export default function PortalDashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hospital, setHospital] = useState<PortalHospital | null>(null);

  useEffect(() => {
    setHospital(getPortalHospital());
    (async () => {
      const result = await portalFetch("/api/portal/dashboard");
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        else setError(result.error);
        return;
      }
      setData(result.data as DashboardData);
    })();
  }, [router]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper px-space-4">
        <p className="text-[14px] text-error">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <PortalSidebar hospital={hospital} active="dashboard" />

      <main className="flex-1 overflow-y-auto p-space-6">
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
            <select
              disabled
              title="Coming soon"
              className="h-9 cursor-not-allowed rounded-md border border-line bg-card px-space-3 text-[13px] text-ink-600"
            >
              <option>All Branches</option>
            </select>
          </div>
        </div>

        {!data ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <>
            <div className="mb-space-4 grid grid-cols-1 gap-space-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Today's appointments" value={data.stats.today_appointments} deltaPct={data.stats.today_appointments_delta_pct} />
              <StatTile label="Confirmed" value={data.stats.confirmed_today} deltaPct={data.stats.confirmed_today_delta_pct} />
              <StatTile label="New patients" value={data.stats.new_patients_today} deltaPct={data.stats.new_patients_today_delta_pct} />
              <StatTile label="No-shows" value={data.stats.no_shows_today} deltaPct={data.stats.no_shows_today_delta_pct} upIsGood={false} />
            </div>

            <div className="mb-space-4 grid grid-cols-1 gap-space-4 lg:grid-cols-2">
              <WeeklyTrendChart data={data.weekly_counts} />
              <DepartmentDonut data={data.department_breakdown} />
            </div>

            <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-2">
              <RecentAppointmentsTable appointments={data.recent_appointments} />
              <ActivityFeed items={data.activity_feed} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
