"use client";

import {
  Activity,
  Building2,
  CheckCircle2,
  ChevronRight,
  Clock,
  CreditCard,
  FileText,
  HeadphonesIcon,
  Megaphone,
  Plus,
  Zap,
} from "lucide-react";
import {
  Area,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { StatTile } from "@/components/portal/StatTile";
import { formatShortDateTime } from "@/lib/formatDate";
import { useSuperAdminDashboard } from "@/hooks/useSuperAdminDashboard";

const TIER_LABELS: Record<string, string> = { tier1: "Tier 1", tier2: "Tier 2", tier3: "Tier 3" };
const TIER_COLORS = ["#2a78d6", "#7c5cf5", "#1baf7a", "#eda100"];

// Everything below has no real backend source yet (no subscription/plan/
// billing/support-ticket/monitoring model in this codebase) -- hardcoded so
// the layout/data-shape matches the target design, wire each one up to a
// real table as soon as it exists. Rendered full-color (not greyed out, per
// explicit feedback) with a small "Mock" badge as the only signal.
const MOCK_RECENT_RENEWALS = [
  { hospital: "Sunrise General Hospital", plan: "Professional", renewalDate: "30 Sep 2025", daysLeft: 7, status: "Expiring Soon" },
  { hospital: "City Care Medical Center", plan: "Enterprise", renewalDate: "12 Oct 2025", daysLeft: 19, status: "Upcoming" },
  { hospital: "Lifeline Specialty Hospital", plan: "Professional", renewalDate: "25 Oct 2025", daysLeft: 32, status: "Upcoming" },
  { hospital: "Metro Health Network", plan: "Enterprise", renewalDate: "02 Nov 2025", daysLeft: 40, status: "Upcoming" },
  { hospital: "Riverside Community Hospital", plan: "Basic", renewalDate: "10 Nov 2025", daysLeft: 48, status: "Upcoming" },
];

const MOCK_SUPPORT_TICKETS = [
  { id: "#4582", hospital: "City Care Medical", subject: "Unable to export reports", priority: "High", status: "Open" },
  { id: "#4581", hospital: "Sunrise General", subject: "Login issues for staff", priority: "Medium", status: "Open" },
  { id: "#4578", hospital: "Lifeline Specialty", subject: "Feature request – Lab Integration", priority: "Low", status: "In Progress" },
  { id: "#4575", hospital: "Metro Health", subject: "Billing module not syncing", priority: "High", status: "Open" },
  { id: "#4573", hospital: "Riverside Community", subject: "Need user access for new staff", priority: "Low", status: "Resolved" },
];

const MOCK_PLATFORM_SERVICES = [
  { name: "Application Services", status: "Operational" },
  { name: "Database", status: "Operational" },
  { name: "Integrations", status: "Operational" },
  { name: "File Storage", status: "Operational" },
];

const RENEWAL_STATUS_CLASSES: Record<string, string> = {
  "Expiring Soon": "bg-amber-100 text-amber-700",
  Upcoming: "bg-blue-100 text-blue-700",
};

const TICKET_PRIORITY_CLASSES: Record<string, string> = {
  High: "bg-red-100 text-red-700",
  Medium: "bg-amber-100 text-amber-700",
  Low: "bg-ink-100 text-ink-600",
};

const TICKET_STATUS_CLASSES: Record<string, string> = {
  Open: "bg-red-100 text-red-700",
  "In Progress": "bg-blue-100 text-blue-700",
  Resolved: "bg-green-100 text-green-700",
};

function Pill({ label, className }: { label: string; className?: string }) {
  return (
    <span className={cn("px-space-2 inline-block rounded-full py-0.5 text-[11px] font-semibold", className)}>
      {label}
    </span>
  );
}

function PanelHeader({
  title,
  subtitle,
  mock,
}: {
  title: string;
  subtitle?: string;
  mock?: boolean;
}) {
  return (
    <div className="mb-space-4 gap-space-3 flex items-start justify-between">
      <div>
        <h3 className="text-label text-ink-900 font-bold">{title}</h3>
        {subtitle && <p className="text-hint mt-space-0.5">{subtitle}</p>}
      </div>
      {mock && <Badge tone="clay">Mock</Badge>}
    </div>
  );
}

function QuickActionButton({
  label,
  icon: Icon,
  href,
  mock,
}: {
  label: string;
  icon: React.ElementType;
  href?: string;
  mock?: boolean;
}) {
  const content = (
    <div
      className={cn(
        "gap-space-3 px-space-3 py-space-3 mb-space-2 flex w-full items-center rounded-md text-left text-[13px] font-semibold transition-colors duration-150",
        href
          ? "bg-brand-600 hover:bg-brand-700 text-white"
          : "border-line bg-card text-ink-900 hover:bg-paper border",
      )}
    >
      <Icon size={16} strokeWidth={2} className="shrink-0" />
      <span className="flex-1">{label}</span>
      {mock && <Badge tone="clay">Mock</Badge>}
      <ChevronRight size={16} className="shrink-0 opacity-70" />
    </div>
  );

  if (href) {
    return (
      <a href={href} className="block">
        {content}
      </a>
    );
  }
  return (
    <button type="button" className="block w-full">
      {content}
    </button>
  );
}

function DashboardContent() {
  const { dashboard, error } = useSuperAdminDashboard();
  const hospitals = dashboard?.hospitals ?? null;

  const growthTrend = (hospitals?.growth_trend ?? []).map((p) => ({
    ...p,
    label: new Date(`${p.month}-01T00:00:00`).toLocaleDateString(undefined, {
      month: "short",
      year: "2-digit",
    }),
    // Mock second series -- no subscriptions table exists yet, this is a
    // rough proportion of the real hospital count just to shape the chart
    // like the target design's two-line trend.
    mock_active_subscriptions: Math.round(p.total_hospitals * 0.86),
  }));

  const statusData = hospitals
    ? [
        { name: "Active", value: hospitals.active, color: "#1baf7a" },
        { name: "Inactive", value: hospitals.inactive, color: "#c3c2b7" },
      ]
    : [];
  const statusTotal = hospitals ? hospitals.total : 0;

  const tierEntries = Object.entries(hospitals?.by_tier ?? {});
  const tierTotal = tierEntries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Super Admin Dashboard</h1>
        <p className="text-ink-600 text-[13px]">
          Overview of all hospitals, subscriptions, revenue, support and platform activity.
        </p>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {/* Top stat row -- same 6 cards as the target design, same order. Only
      Total Hospitals has a real backing table today; the rest carry a Mock badge. */}
      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <StatTile
          label="Total Hospitals"
          value={hospitals ? hospitals.total : null}
          deltaPct={null}
          hint={hospitals ? `+${hospitals.new_this_month} this month` : "Loading…"}
          icon={Building2}
        />
        <StatTile
          label="Active Subscriptions"
          value={36}
          deltaPct={null}
          hint="86% of total hospitals"
          icon={FileText}
          mock
        />
        <StatTile
          label="Monthly Recurring Revenue"
          value={36950}
          deltaPct={12}
          hint="from last month"
          icon={CreditCard}
          prefix="$"
          tint="success"
          mock
        />
        <StatTile
          label="Expiring Renewals"
          value={5}
          deltaPct={null}
          hint="in next 30 days"
          icon={Clock}
          tint="clay"
          mock
        />
        <StatTile
          label="Support Tickets Open"
          value={12}
          deltaPct={-25}
          hint="from last week"
          icon={HeadphonesIcon}
          tint="clay"
          upIsGood={false}
          mock
        />
        <StatTile
          label="Feature Activations"
          value={148}
          deltaPct={18}
          hint="from last month"
          icon={Zap}
          tint="success"
          mock
        />
      </div>

      {/* Row 2: growth trend chart (wide) + hospital status donut + quick actions */}
      <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-4">
        <Card className="p-space-4 lg:col-span-2">
          <PanelHeader
            title="Subscription Growth Trend"
            subtitle="Total Hospitals is real · Active Subscriptions is mock"
          />
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={growthTrend} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="#e1e0d9" vertical={false} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: "#c3c2b7" }}
                tick={{ fontSize: 12, fill: "#898781" }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: "#898781" }}
                allowDecimals={false}
              />
              <Tooltip contentStyle={{ fontSize: 12.5, borderRadius: 8, borderColor: "#e1e0d9" }} />
              <Legend
                verticalAlign="top"
                align="right"
                height={28}
                formatter={(value) => <span className="text-ink-600 text-[12px]">{value}</span>}
              />
              <Area
                type="monotone"
                dataKey="total_hospitals"
                name="Total Hospitals"
                stroke="#00949E"
                fill="#00949E"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="mock_active_subscriptions"
                name="Active Subscriptions (mock)"
                stroke="#7c5cf5"
                strokeDasharray="4 3"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-space-4">
          <PanelHeader title="Hospital Status Overview" />
          {!hospitals ? (
            <p className="text-ink-400 py-space-4 text-center text-[13px]">Loading…</p>
          ) : (
            <div>
              <div className="relative">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={statusData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={50}
                      outerRadius={78}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {statusData.map((s) => (
                        <Cell key={s.name} fill={s.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-ink-900 text-[20px] leading-none font-bold">{statusTotal}</span>
                  <span className="text-ink-400 text-[11px]">Hospitals</span>
                </div>
              </div>
              <ul className="space-y-space-2 mt-space-3">
                {statusData.map((s) => (
                  <li key={s.name} className="gap-space-2 flex items-center text-[12.5px]">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
                    <span className="text-ink-900 flex-1">{s.name}</span>
                    <span className="text-ink-600 font-semibold">
                      {s.value} · {statusTotal ? Math.round((s.value / statusTotal) * 100) : 0}%
                    </span>
                  </li>
                ))}
                <li className="gap-space-2 flex items-center text-[12.5px]">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-400" />
                  <span className="text-ink-900 flex-1">Trial</span>
                  <Badge tone="clay">Mock</Badge>
                </li>
                <li className="gap-space-2 flex items-center text-[12.5px]">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-red-400" />
                  <span className="text-ink-900 flex-1">Suspended</span>
                  <Badge tone="clay">Mock</Badge>
                </li>
              </ul>
            </div>
          )}
        </Card>

        <Card className="p-space-4">
          <PanelHeader title="Quick Actions" subtitle="Common tasks for hospital management" />
          <QuickActionButton label="Add Hospital" icon={Plus} href="/admin/onboard-hospital" />
          <QuickActionButton label="Create Plan" icon={FileText} mock />
          <QuickActionButton label="Send Reminder" icon={Megaphone} mock />
          <QuickActionButton label="View Tickets" icon={HeadphonesIcon} mock />
        </Card>
      </div>

      {/* Row 3: recent renewals + recent support tickets (both mock) */}
      <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-2">
        <Card className="p-space-4">
          <PanelHeader title="Recent Renewals" mock />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead>
                <tr className="text-ink-400 border-line border-b text-[11px] tracking-wide uppercase">
                  <th className="py-space-2 font-semibold">Hospital</th>
                  <th className="py-space-2 font-semibold">Plan</th>
                  <th className="py-space-2 font-semibold">Renewal Date</th>
                  <th className="py-space-2 font-semibold">Days Left</th>
                  <th className="py-space-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-line divide-y">
                {MOCK_RECENT_RENEWALS.map((r) => (
                  <tr key={r.hospital}>
                    <td className="py-space-2.5 text-ink-900 font-semibold">{r.hospital}</td>
                    <td className="py-space-2.5 text-ink-600">{r.plan}</td>
                    <td className="py-space-2.5 text-ink-600">{r.renewalDate}</td>
                    <td className="py-space-2.5 text-ink-600">{r.daysLeft}</td>
                    <td className="py-space-2.5">
                      <Pill label={r.status} className={RENEWAL_STATUS_CLASSES[r.status]} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="p-space-4">
          <PanelHeader title="Recent Support Tickets" mock />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead>
                <tr className="text-ink-400 border-line border-b text-[11px] tracking-wide uppercase">
                  <th className="py-space-2 font-semibold">#</th>
                  <th className="py-space-2 font-semibold">Hospital</th>
                  <th className="py-space-2 font-semibold">Subject</th>
                  <th className="py-space-2 font-semibold">Priority</th>
                  <th className="py-space-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-line divide-y">
                {MOCK_SUPPORT_TICKETS.map((t) => (
                  <tr key={t.id}>
                    <td className="py-space-2.5 text-ink-600">{t.id}</td>
                    <td className="py-space-2.5 text-ink-900 font-semibold">{t.hospital}</td>
                    <td className="py-space-2.5 text-ink-600">{t.subject}</td>
                    <td className="py-space-2.5">
                      <Pill label={t.priority} className={TICKET_PRIORITY_CLASSES[t.priority]} />
                    </td>
                    <td className="py-space-2.5">
                      <Pill label={t.status} className={TICKET_STATUS_CLASSES[t.status]} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Row 4: plan distribution (real, by data_tier) + activity log (real) + platform health (mock) */}
      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-4">
        <Card className="p-space-4">
          <PanelHeader title="Plan Distribution" subtitle="By data connection tier" />
          {tierEntries.length === 0 ? (
            <p className="text-ink-400 py-space-4 text-center text-[13px]">
              {hospitals ? "No hospitals yet." : "Loading…"}
            </p>
          ) : (
            <div>
              <div className="relative">
                <ResponsiveContainer width="100%" height={160}>
                  <PieChart>
                    <Pie
                      data={tierEntries.map(([tier, count]) => ({ name: TIER_LABELS[tier] || tier, value: count }))}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={44}
                      outerRadius={70}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {tierEntries.map(([tier], i) => (
                        <Cell key={tier} fill={TIER_COLORS[i % TIER_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-ink-900 text-[18px] leading-none font-bold">{tierTotal}</span>
                  <span className="text-ink-400 text-[11px]">Hospitals</span>
                </div>
              </div>
              <ul className="space-y-space-2 mt-space-3">
                {tierEntries.map(([tier, count], i) => (
                  <li key={tier} className="gap-space-2 flex items-center text-[12.5px]">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: TIER_COLORS[i % TIER_COLORS.length] }}
                    />
                    <span className="text-ink-900 flex-1">{TIER_LABELS[tier] || tier}</span>
                    <span className="text-ink-600 font-semibold">
                      {count} · {Math.round((count / tierTotal) * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card className="p-space-4 lg:col-span-2">
          <PanelHeader title="Latest Activity Log" subtitle="Real, cross-tenant audit log" />
          {!dashboard ? (
            <p className="text-ink-400 py-space-4 text-center text-[13px]">Loading…</p>
          ) : dashboard.recent_activity.length === 0 ? (
            <p className="text-ink-400 py-space-4 text-center text-[13px]">No activity yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12.5px]">
                <thead>
                  <tr className="text-ink-400 border-line border-b text-[11px] tracking-wide uppercase">
                    <th className="py-space-2 font-semibold">Time</th>
                    <th className="py-space-2 font-semibold">Action</th>
                    <th className="py-space-2 font-semibold">Details</th>
                    <th className="py-space-2 font-semibold">By</th>
                  </tr>
                </thead>
                <tbody className="divide-line divide-y">
                  {dashboard.recent_activity.map((entry) => (
                    <tr key={entry.id}>
                      <td className="py-space-2.5 text-ink-600 whitespace-nowrap">
                        {formatShortDateTime(entry.created_at)}
                      </td>
                      <td className="py-space-2.5">
                        <Pill label={entry.action} className="bg-brand-50 text-brand-700" />
                      </td>
                      <td className="py-space-2.5 text-ink-600">{entry.hospital_name || "—"}</td>
                      <td className="py-space-2.5 text-ink-600">{entry.actor_label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-space-4">
          <PanelHeader title="Platform Health" mock />
          <div className="mb-space-3 gap-space-2 flex items-center">
            <CheckCircle2 size={18} className="text-success shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-ink-900 text-[13px] font-bold">All Systems Operational</p>
            </div>
            <span className="text-ink-600 text-[12px] font-semibold">99.9% uptime</span>
          </div>
          <ul className="space-y-space-2 border-line pt-space-2 border-t">
            {MOCK_PLATFORM_SERVICES.map((s) => (
              <li key={s.name} className="flex items-center justify-between text-[12.5px]">
                <span className="gap-space-2 text-ink-600 flex items-center">
                  <CheckCircle2 size={13} className="text-success shrink-0" /> {s.name}
                </span>
                <span className="text-success font-semibold">{s.status}</span>
              </li>
            ))}
          </ul>
          <div className="border-line mt-space-3 pt-space-2 gap-space-2 flex items-center justify-between border-t">
            <span className="text-ink-400 text-[11px]">Last checked just now</span>
            <Button variant="ghost" className="h-auto! p-0! text-[11.5px]">
              View Status
            </Button>
          </div>
        </Card>
      </div>

      <div className="mt-space-3 gap-space-1 text-ink-400 flex items-center text-[11.5px]">
        <Activity size={12} />
        <span>
          Cards tagged &quot;Mock&quot; have no real data source yet — they&apos;ll be wired up as soon as
          subscriptions/billing/support-tickets/monitoring exist as real tables.
        </span>
      </div>
    </div>
  );
}

export default function SuperAdminDashboardPage() {
  return <DashboardContent />;
}
