import type { ReportAnalyticsData } from "@/hooks/usePortalReportAnalytics";

/** Quotes a CSV field per RFC-4180 (only when it actually needs it) --
 * mirrors lib/csv.ts's own parser assumptions (quoted fields for embedded
 * commas/quotes) so a value like a department name with a comma round-trips
 * correctly in any spreadsheet app. */
function csvField(value: string | number): string {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function toCsvRow(fields: (string | number)[]): string {
  return fields.map(csvField).join(",");
}

/** Builds a client-side CSV export of the currently-loaded report -- there's
 * no backend export endpoint in scope yet (report-analytics is a read-only
 * GET today), so "Export Report" downloads a CSV assembled from the same
 * payload already on screen rather than being a dead/disabled button or a
 * silent no-op. Sectioned (stats, trend, department/visit-type breakdowns,
 * weekly revenue, top departments) with a blank line + header between each,
 * since this is one report with several tables, not one flat dataset. */
export function buildReportCsv(data: ReportAnalyticsData): string {
  const lines: string[] = [];

  lines.push(toCsvRow(["Report Analytics", `${data.date_from} to ${data.date_to}`]));
  lines.push("");

  lines.push(toCsvRow(["Summary"]));
  lines.push(toCsvRow(["Metric", "Value", "Vs previous period"]));
  lines.push(
    toCsvRow([
      "Total Appointments",
      data.stats.total_appointments.value,
      data.stats.total_appointments.delta_pct ?? "",
    ]),
  );
  lines.push(
    toCsvRow([
      "Total Patients",
      data.stats.total_patients.value,
      data.stats.total_patients.delta_pct ?? "",
    ]),
  );
  lines.push(
    toCsvRow([
      "Total Revenue (INR)",
      data.stats.total_revenue.value,
      data.stats.total_revenue.delta_pct ?? "",
    ]),
  );
  lines.push(
    toCsvRow([
      "Occupancy/Utilization Rate (%)",
      data.stats.occupancy_rate.value,
      data.stats.occupancy_rate.delta_pct ?? "",
    ]),
  );
  lines.push("");

  lines.push(toCsvRow(["Appointment Trends"]));
  lines.push(toCsvRow(["Date", "Appointments", "Patients"]));
  for (const p of data.appointment_trends) {
    lines.push(toCsvRow([p.date, p.appointments, p.patients]));
  }
  lines.push("");

  lines.push(toCsvRow(["Appointments by Department"]));
  lines.push(toCsvRow(["Department", "Appointments"]));
  for (const d of data.department_breakdown) {
    lines.push(toCsvRow([d.department_name, d.count]));
  }
  lines.push("");

  lines.push(toCsvRow(["Patient Visit Types"]));
  lines.push(toCsvRow(["Visit Type", "Count"]));
  for (const v of data.visit_type_breakdown) {
    lines.push(toCsvRow([v.visit_type, v.count]));
  }
  lines.push("");

  lines.push(toCsvRow(["Revenue Overview"]));
  lines.push(toCsvRow(["Week", "Revenue (INR)"]));
  for (const w of data.weekly_revenue) {
    lines.push(toCsvRow([w.week_label, w.revenue]));
  }
  lines.push("");

  lines.push(toCsvRow(["Top Performing Departments"]));
  lines.push(toCsvRow(["#", "Department", "Appointments", "Revenue (INR)"]));
  data.top_departments.forEach((d, i) => {
    lines.push(toCsvRow([i + 1, d.department_name, d.appointment_count, d.revenue]));
  });

  return lines.join("\n");
}

/** Triggers a browser download of the report CSV -- same "build a Blob +
 * temporary <a download>" approach as any client-only export (no backend
 * export route exists here yet, see buildReportCsv's own comment). */
export function downloadReportCsv(data: ReportAnalyticsData): void {
  const csv = buildReportCsv(data);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `report-analytics_${data.date_from}_to_${data.date_to}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
