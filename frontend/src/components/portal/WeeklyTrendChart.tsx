"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "@/components/ui/Card";

type Point = { date: string; label: string; count: number };

function TrendTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-card px-space-3 py-space-2 text-[12.5px] shadow-[var(--shadow-md)]">
      <p className="font-semibold text-ink-900">{label}</p>
      <p className="text-ink-600">{payload[0].value} appointments</p>
    </div>
  );
}

export function WeeklyTrendChart({ data }: { data: Point[] }) {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-4 font-bold text-ink-900">Appointment trends (this week)</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="#e1e0d9" vertical={false} />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={{ stroke: "#c3c2b7" }}
            tick={{ fontSize: 12, fill: "#898781" }}
          />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#898781" }} allowDecimals={false} />
          <Tooltip content={<TrendTooltip />} cursor={{ fill: "#00949E", fillOpacity: 0.08 }} />
          <Bar dataKey="count" fill="#00949E" radius={[4, 4, 0, 0]} maxBarSize={40} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
