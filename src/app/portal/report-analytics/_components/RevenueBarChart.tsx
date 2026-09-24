"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Bucket = { week_label: string; revenue: number };

function formatCompactInr(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

type Props = { data: Bucket[]; className?: string };

/** Revenue Overview panel -- same bar-chart config/colors as
 * WeeklyTrendChart.tsx (components/portal), one bar per week in the
 * selected range, with the ₹ value labeled directly above each bar per the
 * reference screenshot (WeeklyTrendChart's own bars don't need a label --
 * this is the one new bit, via recharts' LabelList). */
export function RevenueBarChart({ data, className }: Props) {
  return (
    <Card className={cn("p-space-4", className)}>
      <h3 className="text-label mb-space-4 text-ink-900 font-bold">Revenue Overview</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 20, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="#e1e0d9" vertical={false} />
          <XAxis
            dataKey="week_label"
            tickLine={false}
            axisLine={{ stroke: "#c3c2b7" }}
            tick={{ fontSize: 11, fill: "#898781" }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 12, fill: "#898781" }}
            tickFormatter={(v: number) => formatCompactInr(v)}
            width={64}
          />
          <Bar dataKey="revenue" fill="#00949E" radius={[4, 4, 0, 0]} maxBarSize={48}>
            <LabelList
              dataKey="revenue"
              position="top"
              formatter={(v: number) => formatCompactInr(v)}
              style={{ fontSize: 11, fill: "#4a4842", fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
