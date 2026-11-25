"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card } from "@/components/ui/Card";
import { formatINR } from "@/lib/formatCurrency";

const COLORS = { paid: "#1baf7a", partially_paid: "#eda100", pending: "#e34948" };
const LABELS = { paid: "Paid", partially_paid: "Partially Paid", pending: "Unpaid" };

type Props = {
  billedToday: { paid: number; partially_paid: number; pending: number };
  outstandingAmount: number;
};

function DonutTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-line bg-card px-space-3 py-space-2 rounded-md border text-[12.5px] shadow-[var(--shadow-md)]">
      <p className="text-ink-900 font-semibold">{payload[0].name}</p>
      <p className="text-ink-600">{formatINR(payload[0].value)}</p>
    </div>
  );
}

/** Sales & Billing page's own donut -- today's billed amount split by
 * payment status (not literally "money collected" the way the reference
 * mockup's "Total Collection" center label implies -- that figure is
 * already its own stat tile, computed from actual payment_amount, which
 * can legitimately differ from today's total billed). Labeled "Billed
 * Today" here instead so the two numbers are never confused for the same
 * thing. */
export function CollectionDonut({ billedToday, outstandingAmount }: Props) {
  const slices = (["paid", "partially_paid", "pending"] as const)
    .map((key) => ({ key, label: LABELS[key], value: billedToday[key] }))
    .filter((s) => s.value > 0);
  const total = slices.reduce((sum, s) => sum + s.value, 0);

  return (
    <Card className="p-space-4">
      <div className="mb-space-4 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Payment Collection (Today)</h3>
        <span className="border-line text-ink-600 px-space-2 py-space-1 rounded-md border text-[12px] font-semibold">Today</span>
      </div>

      {total === 0 ? (
        <div className="text-ink-400 flex h-[180px] items-center justify-center text-[13px]">No bills today yet.</div>
      ) : (
        <div className="gap-space-4 flex items-center">
          <div className="relative w-[45%] shrink-0">
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={slices} dataKey="value" nameKey="label" innerRadius={50} outerRadius={78} paddingAngle={slices.length > 1 ? 2 : 0} strokeWidth={0}>
                  {slices.map((s) => <Cell key={s.key} fill={COLORS[s.key]} />)}
                </Pie>
                <Tooltip content={<DonutTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-ink-900 text-[18px] leading-none font-bold">{formatINR(total)}</span>
              <span className="text-ink-400 text-[10.5px]">Billed Today</span>
            </div>
          </div>
          <ul className="space-y-space-2 flex-1">
            {slices.map((s) => (
              <li key={s.key} className="gap-space-2 flex items-center text-[12.5px]">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: COLORS[s.key] }} />
                <span className="text-ink-900 flex-1">{s.label}</span>
                <span className="text-ink-600 font-semibold">{formatINR(s.value)}</span>
                <span className="text-hint w-10 text-right">{Math.round((s.value / total) * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-clay-100 mt-space-4 flex items-center justify-between rounded-md p-3">
        <span className="text-clay-700 text-[12.5px] font-bold">Outstanding Amount</span>
        <span className="text-clay-700 text-[13px] font-bold">{formatINR(outstandingAmount)}</span>
      </div>
    </Card>
  );
}
