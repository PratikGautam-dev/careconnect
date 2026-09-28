"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { AppointmentBillingHospitalRow } from "@/hooks/useAppointmentBilling";

const ONLINE_COLOR = "#00949E";
const CASH_COLOR = "#eda100";
const MAX_HOSPITALS = 8;

function formatCompactInr(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

function truncate(name: string, max = 14): string {
  return name.length > max ? `${name.slice(0, max - 1)}…` : name;
}

type Props = { rows: AppointmentBillingHospitalRow[] | null; className?: string };

/** Appointment Billing overview page's hospital-wise money comparison --
 * top hospitals by total collected, Online vs Cash stacked. Deliberately
 * takes the already-loaded first page of useAppointmentBillingByHospital's
 * data (already sorted total_collected desc) instead of its own fetch --
 * this chart is "free" (zero added latency), matching the "instant, no
 * extra chunk" requirement the rest of this page follows. */
export function HospitalCollectionsBarChart({ rows, className }: Props) {
  const data = (rows ?? [])
    .slice(0, MAX_HOSPITALS)
    .map((r) => ({ name: truncate(r.hospital_name), online: r.online_collected, cash: r.cash_collected }));

  return (
    <Card className={cn("p-space-4", className)}>
      <h3 className="text-label mb-space-4 text-ink-900 font-bold">Collections by Hospital</h3>
      {!rows ? (
        <div className="text-ink-400 flex h-60 items-center justify-center text-[13px]">Loading…</div>
      ) : data.length === 0 ? (
        <div className="text-ink-400 flex h-60 items-center justify-center text-[13px]">
          No collections in this range.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="#e1e0d9" vertical={false} />
            <XAxis
              dataKey="name"
              tickLine={false}
              axisLine={{ stroke: "#c3c2b7" }}
              tick={{ fontSize: 11, fill: "#898781" }}
              interval={0}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "#898781" }}
              tickFormatter={(v: number) => formatCompactInr(v)}
              width={64}
            />
            <Tooltip formatter={(v: number) => formatCompactInr(v)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="online" name="Online" stackId="collected" fill={ONLINE_COLOR} radius={[0, 0, 0, 0]} maxBarSize={40} />
            <Bar dataKey="cash" name="Cash" stackId="collected" fill={CASH_COLOR} radius={[4, 4, 0, 0]} maxBarSize={40} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
