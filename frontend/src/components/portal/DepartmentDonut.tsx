"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card } from "@/components/ui/Card";

type Slice = { department_name: string; count: number };

// dataviz skill's documented default categorical palette, first slots in
// fixed order (never cycled/reassigned) -- validated for adjacent-pair CVD
// separation, which is what a donut/pie's ring of touching neighbors needs.
const SLOT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

function DonutTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-card px-space-3 py-space-2 text-[12.5px] shadow-[var(--shadow-md)]">
      <p className="font-semibold text-ink-900">{payload[0].name}</p>
      <p className="text-ink-600">{payload[0].value} appointments</p>
    </div>
  );
}

export function DepartmentDonut({ data }: { data: Slice[] }) {
  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-4 font-bold text-ink-900">Appointments by department</h3>
      {total === 0 ? (
        <div className="flex h-[220px] items-center justify-center text-[13px] text-ink-400">
          No appointments in the last 30 days.
        </div>
      ) : (
        <div className="flex items-center gap-space-4">
          <ResponsiveContainer width="55%" height={200}>
            <PieChart>
              <Pie
                data={data}
                dataKey="count"
                nameKey="department_name"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={data.length > 1 ? 2 : 0}
                strokeWidth={0}
              >
                {data.map((entry, i) => (
                  <Cell key={entry.department_name} fill={SLOT_COLORS[i % SLOT_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<DonutTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="flex-1 space-y-space-2">
            {data.map((d, i) => (
              <li key={d.department_name} className="flex items-center gap-space-2 text-[12.5px]">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: SLOT_COLORS[i % SLOT_COLORS.length] }}
                />
                <span className="flex-1 truncate text-ink-900">{d.department_name}</span>
                <span className="font-semibold text-ink-600">{Math.round((d.count / total) * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
