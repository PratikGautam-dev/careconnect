"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { AppointmentBillingTrendPoint } from "@/hooks/useAppointmentBilling";

// Same brand-teal-primary convention as the portal's AppointmentTrendsChart/
// the admin dashboard's own Hospital Growth Trend area -- this page lives
// in the super-admin section, so it matches THAT chart's palette rather
// than introducing a third one.
const GROSS_COLOR = "#00949E";
const NET_COLOR = "#1baf7a";
const REFUNDED_COLOR = "#e34948";

function formatCompactInr(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

function formatDayLabel(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function TrendTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-line bg-card px-space-3 py-space-2 rounded-md border text-[12.5px] shadow-[var(--shadow-md)]">
      <p className="text-ink-900 mb-space-1 font-semibold">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-ink-600 gap-space-2 flex items-center justify-between">
          <span className="gap-space-1 flex items-center">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: p.color }} />
            {p.name}
          </span>
          <span className="font-semibold">{formatCompactInr(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

type Props = { data: AppointmentBillingTrendPoint[] | null; className?: string };

/** Appointment Billing overview page's money-trend chart -- same visual
 * slot/pattern as the portal's AppointmentTrendsChart (a 2-3 series line
 * chart over the selected date range), plotting gross collected, net
 * actual (after completed refunds) and refunded per day, fed by
 * useAppointmentBillingTrend. Reused as-is (hospital_id scoped) on the
 * per-tenant detail page. */
export function RevenueTrendChart({ data, className }: Props) {
  const points = (data ?? []).map((p) => ({ ...p, label: formatDayLabel(p.date) }));
  return (
    <Card className={cn("p-space-4", className)}>
      <h3 className="text-label mb-space-2 text-ink-900 font-bold">Money Trend</h3>
      <div className="gap-space-4 mb-space-2 flex flex-wrap items-center text-[12px]">
        <span className="gap-space-1 text-ink-600 flex items-center">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: GROSS_COLOR }} />
          Gross Collected
        </span>
        <span className="gap-space-1 text-ink-600 flex items-center">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: NET_COLOR }} />
          Net Actual
        </span>
        <span className="gap-space-1 text-ink-600 flex items-center">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: REFUNDED_COLOR }} />
          Refunded
        </span>
      </div>
      {!data ? (
        <div className="text-ink-400 flex h-60 items-center justify-center text-[13px]">
          Loading…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="#e1e0d9" vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ stroke: "#c3c2b7" }}
              tick={{ fontSize: 11, fill: "#898781" }}
              minTickGap={20}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "#898781" }}
              tickFormatter={(v: number) => formatCompactInr(v)}
              width={64}
            />
            <Tooltip content={<TrendTooltip />} />
            <Line
              type="monotone"
              dataKey="gross_collected"
              name="Gross Collected"
              stroke={GROSS_COLOR}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="net_actual"
              name="Net Actual"
              stroke={NET_COLOR}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="refunded"
              name="Refunded"
              stroke={REFUNDED_COLOR}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
