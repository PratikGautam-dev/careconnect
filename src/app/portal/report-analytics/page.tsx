"use client";

import { useMemo, useState } from "react";
import { CalendarRange, Download, IndianRupee, PieChart, Users } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { DateRangePicker } from "@/components/ui/DateRangePicker";
import { ExportDialog } from "@/components/export/ExportDialog";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { DepartmentDonut } from "@/components/portal/DepartmentDonut";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePortalReportAnalytics } from "@/hooks/usePortalReportAnalytics";
import { useCsvExport, useExportHistory } from "@/hooks/useExport";
import { formatHeaderDate } from "@/lib/formatDate";
import { portalFetch, portalFetchBlob } from "@/lib/portalAuth";
import { usePermission, useStaffSession } from "@/lib/staffAuth";
import { AppointmentTrendsChart } from "./_components/AppointmentTrendsChart";
import { VisitTypeDonut } from "./_components/VisitTypeDonut";
import { RevenueBarChart } from "./_components/RevenueBarChart";
import { KeyInsightsList } from "./_components/KeyInsightsList";
import { TopDepartmentsTable } from "./_components/TopDepartmentsTable";

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
  // Export is an admin-only action in the portal (confirmed with the user)
  // -- every other staff role sees the same report, just without the
  // Export Report button/dialog.
  const session = useStaffSession();
  const canExport = !!session?.is_admin;
  const [range, setRange] = useState(currentMonthRange);
  const { data, error } = usePortalReportAnalytics(range.from, range.to);
  const today = new Date();

  const [exportOpen, setExportOpen] = useState(false);
  const [exportHistoryPage, setExportHistoryPage] = useState(1);
  const exportMutation = useCsvExport(
    portalFetchBlob,
    "/api/portal/report-analytics/export",
    "report-analytics.csv",
  );
  const exportHistory = useExportHistory(
    portalFetch,
    "/api/portal/exports/history",
    "PORTAL_REPORT_ANALYTICS",
    exportHistoryPage,
    10,
    canExport,
  );

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
              <DateRangePicker
                dateFrom={range.from}
                dateTo={range.to}
                onChange={(from, to) => setRange({ from, to })}
              />
              {/* Its own independent date range, picked inside the dialog --
                  deliberately NOT tied to the DateRangePicker above,
                  same "export has its own From/To" convention every other
                  export in the app follows. Admin-only (canExport). */}
              {canExport && (
                <Button variant="secondary" onClick={() => setExportOpen(true)}>
                  <Download size={15} />
                  Export Report
                </Button>
              )}
            </>
          )
        }
      />

      {canExport && (
        <ExportDialog
          open={exportOpen}
          onOpenChange={setExportOpen}
          title="Report Analytics"
          exportMutation={exportMutation}
          history={exportHistory}
          historyPage={exportHistoryPage}
          onHistoryPageChange={setExportHistoryPage}
        />
      )}

      {!ready ? null : error ? (
        <p className="text-error text-[14px]">{error}</p>
      ) : !data ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <>
          <StatTileGrid cols={4} className="mb-space-4">
            <StatTile
              label="Total Appointments"
              value={data.stats.total_appointments.value}
              icon={CalendarRange}
            />
            <StatTile label="Total Patients" value={data.stats.total_patients.value} icon={Users} />
            <StatTile
              label="Total Revenue"
              value={data.stats.total_revenue.value}
              icon={IndianRupee}
              tint="success"
            />
            <StatTile
              label="Occupancy / Utilization Rate"
              value={data.stats.occupancy_rate.value}
              icon={PieChart}
              tint="clay"
            />
          </StatTileGrid>

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
