"use client";

import { useMemo, useState } from "react";
import {
  BarChart3,
  Clock,
  Download,
  FileDown,
  FlaskConical,
  Pause,
  RefreshCw,
  Send,
  TrendingUp,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { QuickActionButton } from "@/components/portal/QuickActionButton";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { cn } from "@/lib/cn";
import {
  createSubscriptionColumns,
  type SubscriptionRow,
} from "./_components/subscription-columns";

// This whole page is mock: CareConnect has no plan/billing/subscription
// model in the backend yet (only hospitals.data_tier + admin_capabilities +
// enabled_features exist today), so unlike the other admin pages there's no
// real hook to read from here -- every row and every stat is fabricated to
// match the target design 1:1, and every card carries a "Mock" badge so
// that's never ambiguous. Swap in real data source-by-source once a
// subscriptions API exists; the DataTable/StatTile/QuickAction wiring stays
// the same either way.
const MOCK_SUBSCRIPTIONS: SubscriptionRow[] = [
  { id: 1, hospitalName: "ABC Super Specialty Hospital", plan: "Professional", billingCycle: "Annual", startDate: "30 Sep 2025", renewalDate: "30 Sep 2026", paymentStatus: "Paid", seats: 120, status: "Active" },
  { id: 2, hospitalName: "City General Hospital", plan: "Basic", billingCycle: "Monthly", startDate: "12 Jan 2025", renewalDate: "12 Feb 2026", paymentStatus: "Paid", seats: 25, status: "Active" },
  { id: 3, hospitalName: "Lakeside Medical Center", plan: "Professional", billingCycle: "Annual", startDate: "18 Mar 2025", renewalDate: "18 Mar 2026", paymentStatus: "Paid", seats: 80, status: "Active" },
  { id: 4, hospitalName: "Metro Care Hospital", plan: "Enterprise", billingCycle: "Annual", startDate: "05 Feb 2025", renewalDate: "05 Feb 2026", paymentStatus: "Paid", seats: 200, status: "Active" },
  { id: 5, hospitalName: "Sunrise Children's Hospital", plan: "Professional", billingCycle: "Monthly", startDate: "22 Aug 2025", renewalDate: "22 Sep 2025", paymentStatus: "Pending", seats: 60, status: "Renewal Due" },
  { id: 6, hospitalName: "Green Valley Hospital", plan: "Basic", billingCycle: "Monthly", startDate: "10 Sep 2025", renewalDate: "10 Oct 2025", paymentStatus: "Paid", seats: 30, status: "Trial" },
  { id: 7, hospitalName: "Riverside Health Institute", plan: "Professional", billingCycle: "Annual", startDate: "15 Nov 2024", renewalDate: "15 Nov 2025", paymentStatus: "Failed", seats: 75, status: "Expired" },
  { id: 8, hospitalName: "Mountain View Hospital", plan: "Enterprise", billingCycle: "Annual", startDate: "01 Jun 2025", renewalDate: "01 Jun 2026", paymentStatus: "Paid", seats: 150, status: "Active" },
  { id: 9, hospitalName: "Coastal Care Hospital", plan: "Basic", billingCycle: "Monthly", startDate: "20 Jul 2025", renewalDate: "20 Aug 2025", paymentStatus: "Paid", seats: 40, status: "Trial" },
  { id: 10, hospitalName: "Heritage Medical Center", plan: "Professional", billingCycle: "Annual", startDate: "03 Jan 2025", renewalDate: "03 Jan 2026", paymentStatus: "Paid", seats: 95, status: "Active" },
];

const PLAN_OPTIONS = [
  { value: "Basic", label: "Basic" },
  { value: "Professional", label: "Professional" },
  { value: "Enterprise", label: "Enterprise" },
];
const STATUS_OPTIONS = [
  { value: "Active", label: "Active" },
  { value: "Trial", label: "Trial" },
  { value: "Renewal Due", label: "Renewal Due" },
  { value: "Expired", label: "Expired" },
  { value: "Cancelled", label: "Cancelled" },
];
const CYCLE_OPTIONS = [
  { value: "Monthly", label: "Monthly" },
  { value: "Annual", label: "Annual" },
];

const PILL_STATUSES: { key: "all" | SubscriptionRow["status"]; label: string }[] = [
  { key: "all", label: "All" },
  { key: "Active", label: "Active" },
  { key: "Trial", label: "Trial" },
  { key: "Renewal Due", label: "Renewal Due" },
  { key: "Expired", label: "Expired" },
  { key: "Cancelled", label: "Cancelled" },
];

function PanelHeader({ title, subtitle, mock }: { title: string; subtitle?: string; mock?: boolean }) {
  return (
    <div className="mb-space-3 gap-space-3 flex items-start justify-between">
      <div>
        <h3 className="text-label text-ink-900 font-bold">{title}</h3>
        {subtitle && <p className="text-hint mt-space-0.5">{subtitle}</p>}
      </div>
      {mock && <Badge tone="clay">Mock</Badge>}
    </div>
  );
}

export default function SubscriptionsPage() {
  const [search, setSearch] = useState("");
  const [plan, setPlan] = useState("all");
  const [status, setStatus] = useState("all");
  const [cycle, setCycle] = useState("all");
  const [pill, setPill] = useState<"all" | SubscriptionRow["status"]>("all");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const filtered = useMemo(() => {
    return MOCK_SUBSCRIPTIONS.filter((row) => {
      if (search && !row.hospitalName.toLowerCase().includes(search.toLowerCase())) return false;
      if (plan !== "all" && row.plan !== plan) return false;
      if (status !== "all" && row.status !== status) return false;
      if (cycle !== "all" && row.billingCycle !== cycle) return false;
      if (pill !== "all" && row.status !== pill) return false;
      return true;
    });
  }, [search, plan, status, cycle, pill]);

  const counts = useMemo(() => {
    const byStatus: Record<string, number> = {};
    for (const row of MOCK_SUBSCRIPTIONS) byStatus[row.status] = (byStatus[row.status] || 0) + 1;
    return byStatus;
  }, []);

  function toggle(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? new Set(filtered.map((r) => r.id)) : new Set());
  }

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Subscriptions</h1>
        <p className="text-ink-600 text-[13px]">
          Manage hospital subscription records, renewals, and billing across CareConnect.
        </p>
      </div>

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile label="Active Subscriptions" value={36} deltaPct={12} hint="of 42 total hospitals" icon={Users} mock />
        <StatTile label="Trials" value={4} deltaPct={33} hint="Hospitals in trial period" icon={FlaskConical} tint="brand" mock />
        <StatTile label="Renewals This Month" value={5} deltaPct={67} hint="Require attention" icon={Clock} tint="clay" mock />
        <StatTile
          label="Churned Accounts"
          value={2}
          deltaPct={-50}
          upIsGood={false}
          hint="This month"
          icon={Pause}
          tint="error"
          mock
        />
        <StatTile label="Avg. Subscription Value" value={4250} prefix="$" deltaPct={18} hint="Per hospital (annual)" icon={BarChart3} mock />
      </div>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4 mb-space-4">
            <div className="gap-space-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <label className="text-hint mb-space-1 block">Search Hospitals</label>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by hospital name, plan, or location…"
                  className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]"
                />
              </div>
              <div>
                <label className="text-hint mb-space-1 block">Plan</label>
                <FilterSelect value={plan} onChange={setPlan} options={PLAN_OPTIONS} allLabel="All Plans" className="h-10 w-full" />
              </div>
              <div>
                <label className="text-hint mb-space-1 block">Status</label>
                <FilterSelect value={status} onChange={setStatus} options={STATUS_OPTIONS} allLabel="All Statuses" className="h-10 w-full" />
              </div>
              <div>
                <label className="text-hint mb-space-1 block">Billing Cycle</label>
                <FilterSelect value={cycle} onChange={setCycle} options={CYCLE_OPTIONS} allLabel="All Cycles" className="h-10 w-full" />
              </div>
            </div>
          </Card>

          <div className="mb-space-4 gap-space-2 flex flex-wrap items-center justify-between">
            <div className="gap-space-2 flex flex-wrap items-center">
              {PILL_STATUSES.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setPill(key)}
                  className={cn(
                    "px-space-3 py-1.5 gap-space-1 flex items-center rounded-full text-[12.5px] font-semibold transition-colors duration-150",
                    pill === key ? "bg-brand-600 text-white" : "bg-black/[0.04] text-ink-600 hover:bg-black/[0.07]",
                  )}
                >
                  {label} ({key === "all" ? MOCK_SUBSCRIPTIONS.length : counts[key] || 0})
                </button>
              ))}
            </div>
            <button
              type="button"
              className="border-line text-ink-700 gap-space-2 px-space-3 hover:bg-paper flex h-9 items-center rounded-md border text-[12.5px] font-semibold"
            >
              <Download size={14} /> Export
            </button>
          </div>

          <Card className="p-space-4">
            <PanelHeader
              title="Hospital Subscriptions"
              subtitle="View and manage subscription records for all hospital clients."
              mock
            />
            <DataTable<SubscriptionRow>
              columns={createSubscriptionColumns({
                selectedIds,
                onToggle: toggle,
                onToggleAll: toggleAll,
                allSelected: filtered.length > 0 && filtered.every((r) => selectedIds.has(r.id)),
              })}
              data={filtered}
              getRowId={(row) => String(row.id)}
              pageSize={10}
              pageSizeOptions={[10, 25, 50]}
            />
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <PanelHeader title="Subscription Summary" mock />
            <div className="space-y-space-2 text-[12.5px]">
              {[
                ["Total Hospitals", "42"],
                ["Active Subscriptions", "36 (86%)"],
                ["Trial Subscriptions", "4 (10%)"],
                ["Renewal Due (Next 30 Days)", "5 (12%)"],
                ["Expired Subscriptions", "3 (7%)"],
                ["Cancelled Accounts", "2 (5%)"],
                ["Total Annual Contract Value (ACV)", "$178,500"],
                ["Average Subscription Value", "$4,250"],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-ink-400">{label}</span>
                  <span className="text-ink-900 font-semibold">{value}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-space-4">
            <PanelHeader title="Quick Actions" subtitle="Common subscription management actions." mock />
            <QuickActionList
              size="sm"
              columns={2}
              actions={[
                { label: "Upgrade Plan", icon: TrendingUp, onClick: () => {} },
                { label: "Extend Trial", icon: FlaskConical, onClick: () => {} },
                { label: "Pause Subscription", icon: Pause, onClick: () => {} },
                { label: "Send Renewal Reminder", icon: Send, onClick: () => {} },
              ]}
            >
              <QuickActionButton label="Download Invoice" icon={FileDown} size="sm" onClick={() => {}} className="col-span-2" />
            </QuickActionList>
          </Card>

          <Card className="p-space-4">
            <PanelHeader title="Recent Subscription Activities" mock />
            <ul className="divide-line divide-y">
              {[
                { time: "Today, 10:24 AM", action: "Renewal Reminder", details: "Sent to Sunrise Children's Hospital", by: "SA" },
                { time: "Today, 09:15 AM", action: "Plan Upgraded", details: "Green Valley Hospital: Basic → Professional", by: "SA" },
                { time: "08 Sep 2025, 04:32 PM", action: "Payment Failed", details: "Riverside Health Institute: Invoice #INV-2025-4481", by: "SA" },
                { time: "07 Sep 2025, 11:18 AM", action: "Trial Extended", details: "Coastal Care Hospital: Extended by 14 days", by: "SA" },
              ].map((entry, i) => (
                <li key={i} className="py-space-2 gap-space-0.5 flex flex-col text-[12px]">
                  <div className="flex items-center justify-between">
                    <span className="gap-space-1 text-ink-900 flex items-center font-semibold">
                      <RefreshCw size={12} /> {entry.action}
                    </span>
                    <span className="text-ink-400">{entry.time}</span>
                  </div>
                  <span className="text-ink-600">
                    {entry.details} · {entry.by}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
