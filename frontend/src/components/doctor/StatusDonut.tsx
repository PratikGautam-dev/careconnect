"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card } from "@/components/ui/Card";

type Slice = { status: string; count: number };

const STATUS_LABELS: Record<string, string> = {
  booked: "Confirmed", cancelled: "Cancelled", rescheduled: "Rescheduled", attended: "Attended", no_show: "No-show",
};
// Semantic status colors, not the categorical palette DepartmentDonut uses
// -- a status breakdown is a state distribution, not a set of independent
// categories, so green/grey/red/amber reads more truthfully than an
// arbitrary hue cycle would.
const STATUS_COLORS: Record<string, string> = {
  booked: "#1baf7a", attended: "#2a78d6", no_show: "#e34948", cancelled: "#898781", rescheduled: "#eda100",
};

function DonutTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-card px-space-3 py-space-2 text-[12.5px] shadow-[var(--shadow-md)]">
      <p className="font-semibold text-ink-900">{STATUS_LABELS[payload[0].name] || payload[0].name}</p>
      <p className="text-ink-600">{payload[0].value} appointments</p>
    </div>
  );
}

/** Doctor dashboard's status-mix donut -- same visual shape as the shared
 * portal's DepartmentDonut, relabeled for a single doctor's own appointment
 * status breakdown over the last 30 days instead of a hospital-wide
 * department split. */
export function StatusDonut({ data }: { data: Slice[] }) {
  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-4 font-bold text-ink-900">My appointments by status (30 days)</h3>
      {total === 0 ? (
        <div className="flex h-[220px] items-center justify-center text-[13px] text-ink-400">No data yet</div>
      ) : (
        <div className="flex items-center gap-space-4">
          <ResponsiveContainer width="60%" height={200}>
            <PieChart>
              <Pie data={data} dataKey="count" nameKey="status" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {data.map((d) => (
                  <Cell key={d.status} fill={STATUS_COLORS[d.status] || "#c3c2b7"} stroke="var(--card)" strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip content={<DonutTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="space-y-space-2 text-[12.5px]">
            {data.map((d) => (
              <li key={d.status} className="flex items-center gap-space-2">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: STATUS_COLORS[d.status] || "#c3c2b7" }}
                />
                <span className="text-ink-600">{STATUS_LABELS[d.status] || d.status}</span>
                <span className="ml-auto font-semibold text-ink-900">{d.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
