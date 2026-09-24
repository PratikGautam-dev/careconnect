"use client";

import { useMemo, useState } from "react";
import { CalendarRange, Download, IndianRupee, PieChart, Users } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { DepartmentDonut } from "@/components/portal/DepartmentDonut";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePortalReportAnalytics } from "@/hooks/usePortalReportAnalytics";
import { formatHeaderDate } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { AppointmentTrendsChart } from "./_components/AppointmentTrendsChart";
import { VisitTypeDonut } from "./_components/VisitTypeDonut";
import { RevenueBarChart } from "./_components/RevenueBarChart";
import { KeyInsightsList } from "./_components/KeyInsightsList";
import { TopDepartmentsTable } from "./_components/TopDepartmentsTable";
import { ReportDateRangePicker } from "./_components/ReportDateRangePicker";
import { downloadReportCsv } from "./_components/exportReportCsv";

function toDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Default range: the current calendar month (1st -> last day), matching
 * the reference screenshot's own "1 Sep 2026 - 30 Sep 2026" example. */
function currentMonthRange(): { from: string; to: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { from: toDateStr(first), to: toDateStr(last) };
}

/** /portal/report-analytics -- the real hospital-wide analytics page the
 * sidebar's "Report analytics" nav item is meant for (it used to alias
 * /portal/report-review, a different, unrelated frontend-only mock page --
 * see PortalSidebar.tsx's NAV_ITEMS comment and this page's own href fix).
 * Gated on its own "report-analytics" page_key/"view" permission, same
 * pattern as every other portal page (usePortalGuard + usePermission).
 *
 * Data comes from GET /api/portal/report-analytics?date_from=&date_to=
 * (usePortalReportAnalytics.ts) -- that endpoint's exact response shape
 * wasn't finalized when this page was built, so it's built against a
 * reasonable interface (ReportAnalyticsData) matching the reference
 * screenshot's sections; field names there may need small adjustments once
 * the real backend lands (see that hook's own field-by-field comments). */
export default function ReportAnalyticsPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("report-analytics", "view");
  const [range, setRange] = useState(currentMonthRange);
  const { data, error } = usePortalReportAnalytics(range.from, range.to);
  const today = new Date();

  const visitTypeSlices = useMemo(
    () => data?.visit_type_breakdown.map((v) => ({ label: v.visit_type, count: v.count })) ?? [],
    [data],
  );

  // The backend sends one {date, appointments, patients} point per day, no
  // display label -- derive the chart's short x-axis label ("1 Sep") here
  // rather than asking the backend to own frontend formatting.
  const trendPoints = useMemo(
    () =>
      data?.appointment_trends.map((p) => ({
        ...p,
        label: new Date(`${p.date}T00:00:00`).toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
        }),
      })) ?? [],
    [data],
  );

  if (ready && !canView) {
    return (
      <PortalShell hospital={hospital} active="report-analytics">
        <p className="text-ink-400 text-[13px]">You don&apos;t have access to Report Analytics.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="report-analytics">
      <PageHeader
        title="Report Analytics"
        description={formatHeaderDate(today)}
        actions={
          !ready ? null : (
            <>
              <ReportDateRangePicker
                dateFrom={range.from}
                dateTo={range.to}
                onChange={(from, to) => setRange({ from, to })}
              />
              {/* Client-side CSV of the currently-loaded report -- no backend
                  export endpoint exists yet (report-analytics is read-only
                  GET today), see exportReportCsv.ts. Disabled until data has
                  actually loaded rather than silently no-op-ing on click. */}
              <Button
                variant="secondary"
                onClick={() => data && downloadReportCsv(data)}
                disabled={!data}
              >
                <Download size={15} />
                Export Report
              </Button>
            </>
          )
        }
      />

      {!ready ? null : error ? (
        <p className="text-error text-[14px]">{error}</p>
      ) : !data ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <>
          <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Total Appointments"
              value={data.stats.total_appointments.value}
              deltaPct={data.stats.total_appointments.delta_pct}
              hint="vs previous period"
              icon={CalendarRange}
            />
            <StatTile
              label="Total Patients"
              value={data.stats.total_patients.value}
              deltaPct={data.stats.total_patients.delta_pct}
              hint="vs previous period"
              icon={Users}
            />
            <StatTile
              label="Total Revenue"
              value={data.stats.total_revenue.value}
              deltaPct={data.stats.total_revenue.delta_pct}
              hint="vs previous period"
              icon={IndianRupee}
              tint="success"
            />
            <StatTile
              label="Occupancy / Utilization Rate"
              value={data.stats.occupancy_rate.value}
              deltaPct={data.stats.occupancy_rate.delta_pct}
              hint="vs previous period"
              icon={PieChart}
              tint="clay"
            />
          </div>

          <div className="mb-space-4 gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
            <AppointmentTrendsChart data={trendPoints} className="lg:col-span-1" />
            <DepartmentDonut data={data.department_breakdown} />
            <VisitTypeDonut title="Patient Visit Types" data={visitTypeSlices} />
          </div>

          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
            <RevenueBarChart data={data.weekly_revenue} />
            <KeyInsightsList insights={data.key_insights} />
            <TopDepartmentsTable data={data.top_departments} />
          </div>
        </>
      )}
    </PortalShell>
  );
}
