"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { AppointmentBillingStats } from "@/hooks/useAppointmentBilling";
import { formatINR } from "@/lib/formatCurrency";

function formatCompactInr(value: number): string {
  return formatINR(value);
}

function MiniDonut({
  title,
  slices,
}: {
  title: string;
  slices: { name: string; value: number; color: string }[];
}) {
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  return (
    <div>
      <p className="text-ink-600 mb-space-2 text-[12.5px] font-semibold">{title}</p>
      {total === 0 ? (
        <p className="text-ink-400 text-[12.5px]">No collections in this range.</p>
      ) : (
        <div className="gap-space-3 flex items-center">
          <div className="relative h-[84px] w-[84px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={26}
                  outerRadius={40}
                  strokeWidth={0}
                >
                  {slices.map((s) => (
                    <Cell key={s.name} fill={s.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => formatCompactInr(v)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="space-y-space-1 flex-1">
            {slices.map((s) => (
              <li key={s.name} className="gap-space-2 flex items-center text-[12px]">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: s.color }}
                />
                <span className="text-ink-900 flex-1 truncate">{s.name}</span>
                <span className="text-ink-600 font-semibold">
                  {total ? Math.round((s.value / total) * 100) : 0}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

type Props = { stats: AppointmentBillingStats | null; className?: string };

/** Two small donuts sharing one card slot on the Appointment Billing
 * overview page -- Online vs Cash, and Platform's Revenue (gst+platform
 * fee) vs the hospital's own money (everything else gross collected).
 * Both derived purely from the stats object useAppointmentBillingStats
 * already fetched for the stat tiles -- no extra request, so this is
 * "free" the same way HospitalCollectionsBarChart's chart is. */
export function StatSplitDonuts({ stats, className }: Props) {
  return (
    <Card className={cn("p-space-4", className)}>
      {!stats ? (
        <div className="text-ink-400 flex h-60 items-center justify-center text-[13px]">
          Loading…
        </div>
      ) : (
        <div className="space-y-space-5">
          <MiniDonut
            title="Online vs Cash"
            slices={[
              { name: "Online", value: stats.online_collected, color: "#00949E" },
              { name: "Cash", value: stats.cash_collected, color: "#eda100" },
            ]}
          />
          <MiniDonut
            title="Platform's Revenue vs Hospital's Money"
            slices={[
              { name: "Platform's Revenue", value: stats.platform_revenue, color: "#2a78d6" },
              {
                name: "Hospital's Money",
                value: Math.max(stats.gross_collected - stats.platform_revenue, 0),
                color: "#1baf7a",
              },
            ]}
          />
        </div>
      )}
    </Card>
  );
}
