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

type Point = { date: string; label: string; appointments: number; patients: number };

// Same axis/grid/tooltip-surface conventions as WeeklyTrendChart.tsx
// (components/portal) -- brand teal for the primary series, the dataviz
// palette's second categorical slot (DepartmentDonut's SLOT_COLORS[1]) for
// the second, so this reads as "the same charting system, one more line"
// rather than a different chart language.
const APPOINTMENTS_COLOR = "#00949E";
const PATIENTS_COLOR = "#eb6834";

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
          <span className="font-semibold">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

type Props = {
  data: Point[];
  onViewDetails?: () => void;
  className?: string;
};

/** Appointment Trends panel -- extends WeeklyTrendChart's bar-chart pattern
 * into a two-series line chart (Appointments, Patients) over the selected
 * date range, per the reference screenshot. Kept as its own component
 * rather than a WeeklyTrendChart prop, since the mark type itself changes
 * (line vs bar) and the two-series legend/tooltip shape doesn't fit that
 * component's single-series `count` design. */
export function AppointmentTrendsChart({ data, onViewDetails, className }: Props) {
  return (
    <Card className={cn("p-space-4", className)}>
      <div className="mb-space-4 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Appointment Trends</h3>
        {onViewDetails && (
          <button
            type="button"
            onClick={onViewDetails}
            className="text-brand-600 hover:text-brand-700 text-[12.5px] font-semibold"
          >
            View details
          </button>
        )}
      </div>
      <div className="gap-space-4 mb-space-2 flex items-center text-[12px]">
        <span className="gap-space-1 text-ink-600 flex items-center">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: APPOINTMENTS_COLOR }} />
          Appointments
        </span>
        <span className="gap-space-1 text-ink-600 flex items-center">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: PATIENTS_COLOR }} />
          Patients
        </span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
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
            allowDecimals={false}
          />
          <Tooltip content={<TrendTooltip />} />
          <Line
            type="monotone"
            dataKey="appointments"
            name="Appointments"
            stroke={APPOINTMENTS_COLOR}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="patients"
            name="Patients"
            stroke={PATIENTS_COLOR}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
