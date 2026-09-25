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
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { QuickActionButton } from "@/components/portal/QuickActionButton";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { cn } from "@/lib/cn";
import { toast } from "@/lib/toast";
import {
  useAdminSubscriptions,
  type SubscriptionRecord,
  type SubscriptionStatus,
} from "@/hooks/useAdminSubscriptions";
import { useAuditLog } from "@/hooks/useAuditLog";
import { createSubscriptionColumns } from "./_components/subscription-columns";
import { AssignSubscriptionDialog } from "./_components/AssignSubscriptionDialog";

const STATUS_OPTIONS = [
  { value: "trial", label: "Trial" },
  { value: "authorization_pending", label: "Awaiting Payment Setup" },
  { value: "active", label: "Active" },
  { value: "renewal_due", label: "Renewal Due" },
  { value: "expired", label: "Expired" },
  { value: "cancelled", label: "Cancelled" },
  { value: "unassigned", label: "Unassigned" },
];
const CYCLE_OPTIONS = [
  { value: "monthly", label: "Monthly" },
  { value: "annual", label: "Annual" },
];

const PILL_STATUSES: { key: "all" | SubscriptionStatus; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "trial", label: "Trial" },
  { key: "renewal_due", label: "Renewal Due" },
  { key: "expired", label: "Expired" },
  { key: "cancelled", label: "Cancelled" },
  { key: "unassigned", label: "Unassigned" },
];

function PanelHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-space-3 gap-space-3 flex items-start justify-between">
      <div>
        <h3 className="text-label text-ink-900 font-bold">{title}</h3>
        {subtitle && <p className="text-hint mt-space-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function isRenewalThisMonth(renewalDate: string | null): boolean {
  if (!renewalDate) return false;
  const d = new Date(renewalDate);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
}

type ConfirmAction =
  | { type: "unassign"; row: SubscriptionRecord }
  | { type: "cancel-billing"; row: SubscriptionRecord }
  | { type: "bulk-cancel"; rows: SubscriptionRecord[] };

export default function SubscriptionsPage() {
  const {
    subscriptions,
    plans,
    error,
    assign,
    unassign,
    cancelBilling,
    startTrial,
    markManuallyBilled,
    assigning,
    unassigning,
    cancellingBilling,
    startingTrial,
    markingManuallyBilled,
  } = useAdminSubscriptions();
  const { entries: auditEntries } = useAuditLog(null, "platform_admin");

  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [status, setStatus] = useState("all");
  const [cycle, setCycle] = useState("all");
  const [pill, setPill] = useState<"all" | SubscriptionStatus>("all");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState<SubscriptionRecord | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);

  const filtered = useMemo(() => {
    if (!subscriptions) return [];
    return subscriptions.filter((row) => {
      if (search && !row.hospital_name.toLowerCase().includes(search.toLowerCase())) return false;
      if (planFilter !== "all" && String(row.plan_id) !== planFilter) return false;
      if (status !== "all" && row.status !== status) return false;
      if (cycle !== "all" && row.billing_cycle !== cycle) return false;
      if (pill !== "all" && row.status !== pill) return false;
      return true;
    });
  }, [subscriptions, search, planFilter, status, cycle, pill]);

  const counts = useMemo(() => {
    const byStatus: Record<string, number> = {};
    for (const row of subscriptions ?? []) byStatus[row.status] = (byStatus[row.status] || 0) + 1;
    return byStatus;
  }, [subscriptions]);

  const stats = useMemo(() => {
    const all = subscriptions ?? [];
    const active = all.filter((r) => r.status === "active").length;
    const trials = all.filter((r) => r.status === "trial").length;
    const renewalsThisMonth = all.filter((r) => isRenewalThisMonth(r.renewal_date)).length;
    const churned = all.filter((r) => r.status === "cancelled").length;
    const withValue = all.filter((r) => r.monthly_value != null);
    const avgValue = withValue.length
      ? withValue.reduce((sum, r) => sum + (r.monthly_value ?? 0), 0) / withValue.length
      : 0;
    const totalACV = withValue.reduce((sum, r) => sum + (r.monthly_value ?? 0) * 12, 0);
    return { active, trials, renewalsThisMonth, churned, avgValue, totalACV, total: all.length };
  }, [subscriptions]);

  const subscriptionActivity = useMemo(
    () => (auditEntries ?? []).filter((e) => e.entity_type === "hospital_subscription").slice(0, 6),
    [auditEntries],
  );

  function toggle(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? new Set(filtered.map((r) => r.hospital_id)) : new Set());
  }

  function handleUnassign(row: SubscriptionRecord) {
    setConfirmAction({ type: "unassign", row });
  }

  function handleCancelBilling(row: SubscriptionRecord) {
    setConfirmAction({ type: "cancel-billing", row });
  }

  function selectedRecords(): SubscriptionRecord[] {
    return (subscriptions ?? []).filter((r) => selectedIds.has(r.hospital_id));
  }

  async function handleUpgradePlan() {
    const rows = selectedRecords();
    if (rows.length !== 1) {
      toast.error(
        "Select exactly one hospital",
        "Upgrade Plan edits one hospital's subscription at a time.",
      );
      return;
    }
    setEditing(rows[0]);
  }

  async function handleExtendTrial() {
    const rows = selectedRecords().filter((r) => r.status === "trial");
    if (rows.length === 0) {
      toast.error("No trials selected", "Select one or more hospitals currently in trial.");
      return;
    }
    for (const row of rows) {
      const base = row.renewal_date ? new Date(row.renewal_date) : new Date();
      base.setDate(base.getDate() + 14);
      await assign(row.hospital_id, {
        plan_id: row.plan_id as number,
        billing_cycle: row.billing_cycle ?? "monthly",
        status: "trial",
        payment_status: row.payment_status ?? "pending",
        renewal_date: base.toISOString().slice(0, 10),
      });
    }
    toast.success(`Trial extended for ${rows.length} hospital(s)`);
  }

  function handleCancelSubscriptions() {
    const rows = selectedRecords().filter(
      (r) => r.status !== "unassigned" && r.status !== "cancelled",
    );
    if (rows.length === 0) {
      toast.error("Nothing to cancel", "Select one or more active subscriptions first.");
      return;
    }
    setConfirmAction({ type: "bulk-cancel", rows });
  }

  /** Live Razorpay-billed rows (razorpay_subscription_id set) MUST go
   * through cancelBilling (cancels the real subscription first, then the
   * webhook flips status locally) -- the backend's PUT guard rejects
   * status='cancelled' on those rows with a 409 (admin/subscriptions_api.py's
   * _is_billed_and_live check), which is exactly the error this used to
   * surface for every billed hospital swept up in a bulk cancel. Only
   * manual/comped rows (no real billing) go through the direct assign(). */
  async function runConfirmedAction() {
    if (!confirmAction) return;
    if (confirmAction.type === "unassign") {
      await unassign(confirmAction.row.hospital_id, confirmAction.row.hospital_name);
    } else if (confirmAction.type === "cancel-billing") {
      await cancelBilling(confirmAction.row.hospital_id, confirmAction.row.hospital_name);
    } else {
      const billed = confirmAction.rows.filter((r) => r.razorpay_subscription_id);
      const manual = confirmAction.rows.filter((r) => !r.razorpay_subscription_id);
      for (const row of billed) await cancelBilling(row.hospital_id, row.hospital_name);
      for (const row of manual) {
        await assign(row.hospital_id, {
          plan_id: row.plan_id as number,
          billing_cycle: row.billing_cycle ?? "monthly",
          status: "cancelled",
          payment_status: row.payment_status ?? "pending",
        });
      }
    }
    setConfirmAction(null);
  }

  return (
    <div>
      <div className="mb-space-5">
        <h1 className="text-display">Subscriptions</h1>
        <p className="text-ink-600 text-[13px]">
          Manage hospital subscription records, renewals, and billing across CareConnect.
        </p>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile
          label="Active Subscriptions"
          value={stats.active}
          deltaPct={null}
          hint={`of ${stats.total} total hospitals`}
          icon={Users}
        />
        <StatTile
          label="Trials"
          value={stats.trials}
          deltaPct={null}
          hint="Hospitals in trial period"
          icon={FlaskConical}
          tint="brand"
        />
        <StatTile
          label="Renewals This Month"
          value={stats.renewalsThisMonth}
          deltaPct={null}
          hint="Require attention"
          icon={Clock}
          tint="clay"
        />
        <StatTile
          label="Churned Accounts"
          value={stats.churned}
          deltaPct={null}
          upIsGood={false}
          hint="Cancelled"
          icon={Pause}
          tint="error"
        />
        <StatTile
          label="Avg. Subscription Value"
          value={Math.round(stats.avgValue)}
          prefix="₹"
          deltaPct={null}
          hint="Per hospital (monthly)"
          icon={BarChart3}
        />
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
                  placeholder="Search by hospital name…"
                  className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]"
                />
              </div>
              <div>
                <label className="text-hint mb-space-1 block">Plan</label>
                <FilterSelect
                  value={planFilter}
                  onChange={setPlanFilter}
                  options={plans.map((p) => ({ value: String(p.id), label: p.name }))}
                  allLabel="All Plans"
                  className="h-10 w-full"
                />
              </div>
              <div>
                <label className="text-hint mb-space-1 block">Status</label>
                <FilterSelect
                  value={status}
                  onChange={setStatus}
                  options={STATUS_OPTIONS}
                  allLabel="All Statuses"
                  className="h-10 w-full"
                />
              </div>
              <div>
                <label className="text-hint mb-space-1 block">Billing Cycle</label>
                <FilterSelect
                  value={cycle}
                  onChange={setCycle}
                  options={CYCLE_OPTIONS}
                  allLabel="All Cycles"
                  className="h-10 w-full"
                />
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
                    "px-space-3 gap-space-1 flex items-center rounded-full py-1.5 text-[12.5px] font-semibold transition-colors duration-150",
                    pill === key
                      ? "bg-brand-600 text-white"
                      : "text-ink-600 bg-black/4 hover:bg-black/7",
                  )}
                >
                  {label} ({key === "all" ? (subscriptions?.length ?? 0) : counts[key] || 0})
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() =>
                toast.error("Not available yet", "Export needs a real report pipeline.")
              }
              className="border-line text-ink-700 gap-space-2 px-space-3 hover:bg-paper flex h-9 items-center rounded-md border text-[12.5px] font-semibold"
            >
              <Download size={14} /> Export
            </button>
          </div>

          <Card className="p-space-4">
            <PanelHeader
              title="Hospital Subscriptions"
              subtitle="View and manage subscription records for all hospital clients."
            />
            {!subscriptions ? (
              <p className="text-ink-400 text-[13px]">Loading…</p>
            ) : (
              <DataTable<SubscriptionRecord>
                columns={createSubscriptionColumns({
                  selectedIds,
                  onToggle: toggle,
                  onToggleAll: toggleAll,
                  allSelected:
                    filtered.length > 0 && filtered.every((r) => selectedIds.has(r.hospital_id)),
                  onEdit: setEditing,
                  onUnassign: handleUnassign,
                  onCancelBilling: handleCancelBilling,
                })}
                data={filtered}
                getRowId={(row) => String(row.hospital_id)}
                pageSize={10}
                pageSizeOptions={[10, 25, 50]}
              />
            )}
          </Card>

          {editing && (
            <AssignSubscriptionDialog
              open={!!editing}
              onOpenChange={(open) => !open && setEditing(null)}
              record={editing}
              plans={plans}
              onStartTrial={startTrial}
              onMarkManuallyBilled={markManuallyBilled}
              startingTrial={startingTrial}
              markingManuallyBilled={markingManuallyBilled}
            />
          )}
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <PanelHeader title="Subscription Summary" />
            <div className="space-y-space-2 text-[12.5px]">
              {[
                ["Total Hospitals", String(stats.total)],
                [
                  "Active Subscriptions",
                  `${counts.active || 0} (${stats.total ? Math.round(((counts.active || 0) / stats.total) * 100) : 0}%)`,
                ],
                [
                  "Trial Subscriptions",
                  `${counts.trial || 0} (${stats.total ? Math.round(((counts.trial || 0) / stats.total) * 100) : 0}%)`,
                ],
                [
                  "Renewal Due",
                  `${counts.renewal_due || 0} (${stats.total ? Math.round(((counts.renewal_due || 0) / stats.total) * 100) : 0}%)`,
                ],
                [
                  "Expired Subscriptions",
                  `${counts.expired || 0} (${stats.total ? Math.round(((counts.expired || 0) / stats.total) * 100) : 0}%)`,
                ],
                [
                  "Cancelled Accounts",
                  `${counts.cancelled || 0} (${stats.total ? Math.round(((counts.cancelled || 0) / stats.total) * 100) : 0}%)`,
                ],
                [
                  "Total Annual Contract Value (ACV)",
                  `₹${Math.round(stats.totalACV).toLocaleString("en-IN")}`,
                ],
                [
                  "Average Subscription Value",
                  `₹${Math.round(stats.avgValue).toLocaleString("en-IN")}`,
                ],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-ink-400">{label}</span>
                  <span className="text-ink-900 font-semibold">{value}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-space-4">
            <PanelHeader title="Quick Actions" subtitle="Common subscription management actions." />
            <QuickActionList
              size="sm"
              columns={2}
              actions={[
                { label: "Upgrade Plan", icon: TrendingUp, onClick: handleUpgradePlan },
                { label: "Extend Trial", icon: FlaskConical, onClick: handleExtendTrial },
                { label: "Cancel Subscription", icon: Pause, onClick: handleCancelSubscriptions },
                {
                  label: "Send Renewal Reminder",
                  icon: Send,
                  onClick: () =>
                    toast.error("Not available yet", "No notification system exists yet."),
                },
              ]}
            >
              <QuickActionButton
                label="Download Invoice"
                icon={FileDown}
                size="sm"
                onClick={() => toast.error("Not available yet", "No invoice model exists yet.")}
                className="col-span-2"
              />
            </QuickActionList>
          </Card>

          <Card className="p-space-4">
            <PanelHeader title="Recent Subscription Activities" />
            {!auditEntries ? (
              <p className="text-ink-400 py-space-3 text-center text-[12.5px]">Loading…</p>
            ) : subscriptionActivity.length === 0 ? (
              <p className="text-ink-400 py-space-3 text-center text-[12.5px]">No changes yet.</p>
            ) : (
              <ul className="divide-line divide-y">
                {subscriptionActivity.map((entry) => (
                  <li key={entry.id} className="py-space-2 gap-space-0.5 flex flex-col text-[12px]">
                    <div className="flex items-center justify-between">
                      <span className="gap-space-1 text-ink-900 flex items-center font-semibold">
                        <RefreshCw size={12} /> {entry.action}
                      </span>
                      <span className="text-ink-400">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                    </div>
                    <span className="text-ink-600">
                      {entry.hospital_name ?? "—"} · {entry.actor_label}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={!!confirmAction}
        title={
          confirmAction?.type === "unassign"
            ? "Unassign Subscription"
            : confirmAction?.type === "cancel-billing"
              ? "Cancel Billing"
              : "Cancel Subscriptions"
        }
        message={
          confirmAction?.type === "unassign"
            ? `Unassign ${confirmAction.row.hospital_name} from ${confirmAction.row.plan_name}?`
            : confirmAction?.type === "cancel-billing"
              ? `Cancel ${confirmAction.row.hospital_name}'s live Razorpay subscription? This stops their billing.`
              : confirmAction?.type === "bulk-cancel"
                ? `Cancel ${confirmAction.rows.length} subscription(s)? Hospitals on live Razorpay billing will have their real subscription cancelled; others are marked cancelled directly.`
                : ""
        }
        confirmLabel={confirmAction?.type === "unassign" ? "Unassign" : "Cancel"}
        destructive
        busy={assigning || unassigning || cancellingBilling}
        onConfirm={runConfirmedAction}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}
