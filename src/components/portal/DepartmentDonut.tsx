"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Slice = { department_name: string; count: number };

// dataviz skill's documented default categorical palette, first slots in
// fixed order (never cycled/reassigned) -- validated for adjacent-pair CVD
// separation, which is what a donut/pie's ring of touching neighbors needs.
const SLOT_COLORS = [
  "#2a78d6",
  "#eb6834",
  "#1baf7a",
  "#eda100",
  "#e87ba4",
  "#008300",
  "#4a3aa7",
  "#e34948",
];

function DonutTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { name: string; value: number }[];
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-line bg-card px-space-3 py-space-2 rounded-md border text-[12.5px] shadow-[var(--shadow-md)]">
      <p className="text-ink-900 font-semibold">{payload[0].name}</p>
      <p className="text-ink-600">{payload[0].value} appointments</p>
    </div>
  );
}

export function DepartmentDonut({ data, className }: { data: Slice[]; className?: string }) {
  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <Card className={cn("p-space-4", className)}>
      <h3 className="text-label mb-space-4 text-ink-900 font-bold">Appointments by department</h3>
      {total === 0 ? (
        <div className="text-ink-400 flex h-[220px] items-center justify-center text-[13px]">
          No appointments in the last 30 days or scheduled in the next 30.
        </div>
      ) : (
        <div className="gap-space-4 flex items-center">
          <div className="relative w-[55%] shrink-0">
            <ResponsiveContainer width="100%" height={200}>
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
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-ink-900 text-[22px] leading-none font-bold">{total}</span>
              <span className="text-ink-400 text-[11px]">Total</span>
            </div>
          </div>
          <ul className="space-y-space-2 max-h-47.5 flex-1 overflow-y-auto">
            {data.map((d, i) => (
              <li key={d.department_name} className="gap-space-2 flex items-center text-[12.5px]">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: SLOT_COLORS[i % SLOT_COLORS.length] }}
                />
                <span className="text-ink-900 flex-1 truncate">{d.department_name}</span>
                <span className="text-ink-600 font-semibold">
                  {Math.round((d.count / total) * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
