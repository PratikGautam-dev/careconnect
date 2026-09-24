"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Slice = { label: string; count: number };

// Same dataviz-skill categorical palette (fixed slot order) as
// DepartmentDonut.tsx -- kept as its own copy rather than importing that
// component's internal constant, since DepartmentDonut hardcodes
// department_name as its data key/label and this panel's slices
// (New Patients / Follow-up / Diagnostic-Lab / Report Review) aren't
// departments; duplicating the small color list keeps that component's
// props untouched for its existing Dashboard caller.
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
      <p className="text-ink-600">{payload[0].value} visits</p>
    </div>
  );
}

type Props = {
  title: string;
  data: Slice[];
  emptyMessage?: string;
  className?: string;
};

/** Patient Visit Types panel -- same donut-plus-legend visual as
 * DepartmentDonut.tsx (identical inner/outer radius, center total,
 * scrollable legend with count+% rows), generalized over a plain
 * {label,count} slice instead of department_name so it can plot any
 * breakdown (visit types here; nothing today needs a third caller). */
export function VisitTypeDonut({ title, data, emptyMessage, className }: Props) {
  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <Card className={cn("p-space-4", className)}>
      <h3 className="text-label mb-space-4 text-ink-900 font-bold">{title}</h3>
      {total === 0 ? (
        <div className="text-ink-400 flex h-[220px] items-center justify-center text-[13px]">
          {emptyMessage ?? "No data for the selected date range."}
        </div>
      ) : (
        <div className="gap-space-4 flex items-center">
          <div className="relative w-[55%] shrink-0">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={data}
                  dataKey="count"
                  nameKey="label"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={data.length > 1 ? 2 : 0}
                  strokeWidth={0}
                >
                  {data.map((entry, i) => (
                    <Cell key={entry.label} fill={SLOT_COLORS[i % SLOT_COLORS.length]} />
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
              <li key={d.label} className="gap-space-2 flex items-center text-[12.5px]">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: SLOT_COLORS[i % SLOT_COLORS.length] }}
                />
                <span className="text-ink-900 flex-1 truncate">{d.label}</span>
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
