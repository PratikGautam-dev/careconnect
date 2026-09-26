"use client";

import { useMemo } from "react";
import {
  Activity,
  Building2,
  Calendar,
  ChevronRight,
  Clock,
  CreditCard,
  FileText,
  HeadphonesIcon,
  Megaphone,
  Plus,
  Receipt,
} from "lucide-react";
import {
  Area,
  CartesianGrid,
  Cell,
  ComposedChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { StatTile } from "@/components/portal/StatTile";
import { QuickActions, type QuickAction } from "@/components/portal/QuickActions";
import { useAdminBillingRecords } from "@/hooks/useAdminBillingRecords";
import { useAdminSubscriptions, type SubscriptionRecord } from "@/hooks/useAdminSubscriptions";
import { useSuperAdminDashboard } from "@/hooks/useSuperAdminDashboard";
import {
  activityColumns,
  billingRecordColumns,
  renewalColumns,
  ticketColumns,
  type MockTicket,
} from "./_components/dashboard-columns";

const TIER_LABELS: Record<string, string> = { tier1: "Tier 1", tier2: "Tier 2", tier3: "Tier 3" };
const PLAN_COLORS = ["#2a78d6", "#7c5cf5", "#1baf7a", "#eda100", "#c3c2b7"];

// Only table/tile left backed by mock data -- there's no support-ticket
// model in this codebase yet. Everything else on this page (stats, both
// donuts, both tables, the growth chart, activity log) reads real data.
const MOCK_SUPPORT_TICKETS: MockTicket[] = [
  {
    id: "#4582",
    hospital: "City Care Medical",
    subject: "Unable to export reports",
    priority: "High",
    status: "Open",
  },
  {
    id: "#4581",
    hospital: "Sunrise General",
    subject: "Login issues for staff",
    priority: "Medium",
    status: "Open",
  },
  {
    id: "#4578",
    hospital: "Lifeline Specialty",
    subject: "Feature request – Lab Integration",
    priority: "Low",
    status: "In Progress",
  },
  {
    id: "#4575",
    hospital: "Metro Health",
    subject: "Billing module not syncing",
    priority: "High",
    status: "Open",
  },
  {
    id: "#4573",
    hospital: "Riverside Community",
    subject: "Need user access for new staff",
    priority: "Low",
    status: "Resolved",
  },
];

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

// Renewal_date within this many days counts as "expiring soon" -- same
// window the Recent Renewals table's own "days left" highlighting and the
// stat tile share, so the number in the tile always matches what the badge
// styling implies.
const EXPIRING_WINDOW_DAYS = 30;
// Statuses that represent a currently-billed hospital (mirrors
// subscription-columns.tsx's LIVE_BILLING_STATUSES plus "active"/"trial",
// i.e. anything that isn't unassigned/expired/cancelled).
const LIVE_STATUSES = new Set(["trial", "authorization_pending", "active", "renewal_due"]);

function daysUntil(iso: string): number {
  const ms = new Date(`${iso}T00:00:00`).getTime() - new Date(new Date().toDateString()).getTime();
  return Math.round(ms / 86_400_000);
}

function DashboardContent() {
  const { dashboard, error } = useSuperAdminDashboard();
  const { subscriptions, error: subscriptionsError } = useAdminSubscriptions();
  const { records: billingRecords, error: billingError } = useAdminBillingRecords();
  const hospitals = dashboard?.hospitals ?? null;

  const growthTrend = (hospitals?.growth_trend ?? []).map((p) => ({
    ...p,
    label: new Date(`${p.month}-01T00:00:00`).toLocaleDateString(undefined, {
      month: "short",
      year: "2-digit",
    }),
  }));

  const tierEntries = Object.entries(hospitals?.by_tier ?? {});
  const tierTotal = tierEntries.reduce((sum, [, count]) => sum + count, 0);

  const subscriptionStats = useMemo(() => {
    if (!subscriptions) return null;
    const activeCount = subscriptions.filter((s) => s.status === "active").length;
    const mrr = subscriptions
      .filter((s) => s.status === "active" && s.monthly_value != null)
      .reduce((sum, s) => sum + (s.monthly_value ?? 0), 0);
    const expiring = subscriptions.filter(
      (s) =>
        LIVE_STATUSES.has(s.status) &&
        s.renewal_date &&
        daysUntil(s.renewal_date) >= 0 &&
        daysUntil(s.renewal_date) <= EXPIRING_WINDOW_DAYS,
    );
    const upcomingRenewals = subscriptions
      .filter((s): s is SubscriptionRecord & { renewal_date: string } => Boolean(s.renewal_date))
      .sort((a, b) => a.renewal_date.localeCompare(b.renewal_date))
      .slice(0, 8);

    const byStatus: Record<string, number> = {};
    for (const s of subscriptions) byStatus[s.status] = (byStatus[s.status] ?? 0) + 1;

    const planCounts = new Map<string, number>();
    for (const s of subscriptions) {
      const key = s.plan_name ?? "Unassigned";
      planCounts.set(key, (planCounts.get(key) ?? 0) + 1);
    }

    return { activeCount, mrr, expiringCount: expiring.length, upcomingRenewals, byStatus, planCounts };
  }, [subscriptions]);

  const statusData = subscriptionStats
    ? Object.entries(subscriptionStats.byStatus)
        .filter(([, count]) => count > 0)
        .map(([status, count]) => ({
          name:
            status === "unassigned"
              ? "Unassigned"
              : status === "authorization_pending"
                ? "Awaiting Payment"
                : status.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()),
          value: count,
          color:
            status === "active"
              ? "#1baf7a"
              : status === "trial"
                ? "#00949E"
                : status === "renewal_due"
                  ? "#eda100"
                  : status === "authorization_pending"
                    ? "#7c5cf5"
                    : status === "expired" || status === "cancelled"
                      ? "#d8735f"
                      : "#c3c2b7",
        }))
    : [];
  const statusTotal = statusData.reduce((sum, s) => sum + s.value, 0);

  const planEntries = subscriptionStats ? [...subscriptionStats.planCounts.entries()] : [];
  const planTotal = planEntries.reduce((sum, [, count]) => sum + count, 0);

  const combinedError = error || subscriptionsError || billingError;

  // Same shared QuickActionButton/QuickActions the portal dashboard uses
  // (src/components/portal/QuickActions.tsx) -- no separate admin-only
  // button component. "disabled" + a title stands in for the old "mock"
  // badge for the two actions with no real destination yet, matching
  // DashboardQuickActions' own "Export report" pattern.
  const quickActions: QuickAction[] = [
    { label: "Add Hospital", icon: Plus, href: "/admin/onboard-hospital" },
    { label: "Manage Subscriptions", icon: FileText, href: "/admin/subscriptions" },
    { label: "Manage Plans", icon: Receipt, href: "/admin/plans-billing" },
    { label: "Send Reminder", icon: Megaphone, disabled: true, title: "Coming soon" },
    { label: "View Tickets", icon: HeadphonesIcon, disabled: true, title: "Coming soon" },
  ];

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Super Admin Dashboard</h1>
        <p className="text-ink-600 text-[13px]">
          Overview of all hospitals, subscriptions, revenue, support and platform activity.
        </p>
      </div>

      {combinedError && <p className="mb-space-4 text-error text-[13px]">{combinedError}</p>}

      {/* Top stat row -- real everywhere except Support Tickets Open, which
      has no backend model to read from yet. */}
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
          value={subscriptionStats ? subscriptionStats.activeCount : null}
          deltaPct={null}
          hint={
            hospitals && subscriptionStats
              ? `${Math.round((subscriptionStats.activeCount / Math.max(hospitals.total, 1)) * 100)}% of total hospitals`
              : "Loading…"
          }
          icon={FileText}
        />
        <StatTile
          label="Monthly Recurring Revenue"
          value={subscriptionStats ? Math.round(subscriptionStats.mrr) : null}
          deltaPct={null}
          hint="from active subscriptions"
          icon={CreditCard}
          prefix="₹"
          tint="success"
        />
        <StatTile
          label="Expiring Renewals"
          value={subscriptionStats ? subscriptionStats.expiringCount : null}
          deltaPct={null}
          hint={`in next ${EXPIRING_WINDOW_DAYS} days`}
          icon={Clock}
          tint="clay"
        />
        <StatTile
          label="Total Bookings"
          value={dashboard ? dashboard.total_bookings : null}
          deltaPct={null}
          hint="all-time, across hospitals"
          icon={Calendar}
        />
        <StatTile
          label="Support Tickets Open"
          value={12}
          deltaPct={null}
          hint="from last week"
          icon={HeadphonesIcon}
          tint="clay"
          upIsGood={false}
          mock
        />
      </div>

      {/* Row 2: growth trend chart (wide) + subscription status donut + quick actions */}
      <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-4">
        <Card className="p-space-4 lg:col-span-2">
          <PanelHeader title="Hospital Growth Trend" subtitle="Total hospitals over time" />
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
              <Area
                type="monotone"
                dataKey="total_hospitals"
                name="Total Hospitals"
                stroke="#00949E"
                fill="#00949E"
                fillOpacity={0.15}
                strokeWidth={2}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-space-4">
          <PanelHeader title="Subscription Status" subtitle="Across all hospitals" />
          {!subscriptionStats ? (
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
                  <span className="text-ink-900 text-[20px] leading-none font-bold">
                    {statusTotal}
                  </span>
                  <span className="text-ink-400 text-[11px]">Hospitals</span>
                </div>
              </div>
              <ul className="space-y-space-2 mt-space-3">
                {statusData.map((s) => (
                  <li key={s.name} className="gap-space-2 flex items-center text-[12.5px]">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: s.color }}
                    />
                    <span className="text-ink-900 flex-1">{s.name}</span>
                    <span className="text-ink-600 font-semibold">
                      {s.value} · {statusTotal ? Math.round((s.value / statusTotal) * 100) : 0}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <QuickActions title="Quick Actions" actions={quickActions} />
      </div>

      {/* Row 3: recent renewals (real) + recent support tickets (mock) */}
      <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-2">
        <Card className="p-space-4">
          <PanelHeader title="Recent Renewals" subtitle="Soonest upcoming, real subscriptions" />
          <DataTable
            columns={renewalColumns}
            data={subscriptionStats?.upcomingRenewals ?? []}
            getRowId={(row) => String(row.hospital_id)}
            loading={!subscriptionStats}
            emptyMessage="No upcoming renewals."
            pageSize={5}
          />
        </Card>

        <Card className="p-space-4">
          <PanelHeader title="Recent Support Tickets" mock />
          <DataTable
            columns={ticketColumns}
            data={MOCK_SUPPORT_TICKETS}
            getRowId={(row) => row.id}
            pageSize={5}
          />
        </Card>
      </div>

      {/* Row 4: plan distribution (real) + activity log (real) + recent billing records (real) */}
      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-4">
        <Card className="p-space-4">
          <PanelHeader title="Plan Distribution" subtitle="Hospitals per plan" />
          {planEntries.length === 0 ? (
            <p className="text-ink-400 py-space-4 text-center text-[13px]">
              {subscriptionStats ? "No hospitals yet." : "Loading…"}
            </p>
          ) : (
            <div>
              <div className="relative">
                <ResponsiveContainer width="100%" height={160}>
                  <PieChart>
                    <Pie
                      data={planEntries.map(([name, count]) => ({ name, value: count }))}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={44}
                      outerRadius={70}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {planEntries.map(([name], i) => (
                        <Cell key={name} fill={PLAN_COLORS[i % PLAN_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-ink-900 text-[18px] leading-none font-bold">
                    {planTotal}
                  </span>
                  <span className="text-ink-400 text-[11px]">Hospitals</span>
                </div>
              </div>
              <ul className="space-y-space-2 mt-space-3">
                {planEntries.map(([name, count], i) => (
                  <li key={name} className="gap-space-2 flex items-center text-[12.5px]">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: PLAN_COLORS[i % PLAN_COLORS.length] }}
                    />
                    <span className="text-ink-900 flex-1">{name}</span>
                    <span className="text-ink-600 font-semibold">
                      {count} · {planTotal ? Math.round((count / planTotal) * 100) : 0}%
                    </span>
                  </li>
                ))}
              </ul>
              {tierEntries.length > 0 && (
                <p className="text-ink-400 mt-space-3 border-line pt-space-2 border-t text-[11px]">
                  By data tier: {tierEntries.map(([t, c]) => `${TIER_LABELS[t] || t} ${c}`).join(" · ")}
                  {` (${tierTotal} total)`}
                </p>
              )}
            </div>
          )}
        </Card>

        <Card className="p-space-4 lg:col-span-2">
          <PanelHeader title="Latest Activity Log" subtitle="Real, cross-tenant audit log" />
          <DataTable
            columns={activityColumns}
            data={dashboard?.recent_activity ?? []}
            getRowId={(row) => String(row.id)}
            loading={!dashboard}
            emptyMessage="No activity yet."
            pageSize={8}
          />
        </Card>

        <Card className="p-space-4">
          <PanelHeader title="Recent Billing Records" subtitle="Real payments ledger" />
          <DataTable
            columns={billingRecordColumns}
            data={billingRecords?.slice(0, 5) ?? []}
            getRowId={(row) => String(row.id)}
            loading={!billingRecords}
            emptyMessage="No billing records yet."
            pageSize={5}
          />
          <a
            href="/admin/plans-billing"
            className="text-brand-600 mt-space-3 gap-space-1 flex items-center text-[12px] font-semibold"
          >
            View all billing records <ChevronRight size={13} />
          </a>
        </Card>
      </div>

      <div className="mt-space-3 gap-space-1 text-ink-400 flex items-center text-[11.5px]">
        <Activity size={12} />
        <span>
          Only the &quot;Support Tickets&quot; card is mock data -- there&apos;s no support-ticket
          model in this codebase yet. Everything else on this page is real.
        </span>
      </div>
    </div>
  );
}

export default function SuperAdminDashboardPage() {
  return <DashboardContent />;
}
