"use client";

import { useMemo, useState } from "react";
import { BarChart3, Clock, Download, FlaskConical, Pause, Users } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DataTable } from "@/components/ui/DataTable";
import { ExportDialog } from "@/components/export/ExportDialog";
import { FilterActions } from "@/components/portal/FilterActions";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { AuditActivityTable } from "@/components/audit/AuditActivityTable";
import { adminFetch, adminFetchBlob } from "@/lib/adminAuth";
import { formatINR } from "@/lib/formatCurrency";
import { toast } from "@/lib/toast";
import { useCsvExport, useExportHistory } from "@/hooks/useExport";
import { useAdminSubscriptions, type SubscriptionRecord } from "@/hooks/useAdminSubscriptions";
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

  // Draft -- bound directly to the filter inputs below, doesn't affect
  // `filtered` until applyFilters() runs (the Filter button). Same
  // staged-then-Apply pattern as the portal's own useAppointments.ts, so
  // picking a status/plan/cycle doesn't silently re-filter the table out
  // from under you mid-read -- you choose when it takes effect.
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [status, setStatus] = useState("all");
  const [cycle, setCycle] = useState("all");
  // Applied -- what `filtered` actually uses.
  const [appliedSearch, setAppliedSearch] = useState("");
  const [appliedPlanFilter, setAppliedPlanFilter] = useState("all");
  const [appliedStatus, setAppliedStatus] = useState("all");
  const [appliedCycle, setAppliedCycle] = useState("all");
  const [editing, setEditing] = useState<SubscriptionRecord | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportHistoryPage, setExportHistoryPage] = useState(1);

  const exportMutation = useCsvExport(
    adminFetchBlob,
    "/api/admin/subscriptions/export",
    "hospital-subscriptions.csv",
  );
  const exportHistory = useExportHistory(
    adminFetch,
    "/api/admin/exports/history",
    "HOSPITAL_SUBSCRIPTIONS",
    exportHistoryPage,
  );

  const filtered = useMemo(() => {
    if (!subscriptions) return [];
    return subscriptions.filter((row) => {
      if (appliedSearch && !row.hospital_name.toLowerCase().includes(appliedSearch.toLowerCase())) {
        return false;
      }
      if (appliedPlanFilter !== "all" && String(row.plan_id) !== appliedPlanFilter) return false;
      if (appliedStatus !== "all" && row.status !== appliedStatus) return false;
      if (appliedCycle !== "all" && row.billing_cycle !== appliedCycle) return false;
      return true;
    });
  }, [subscriptions, appliedSearch, appliedPlanFilter, appliedStatus, appliedCycle]);

  function applyFilters() {
    setAppliedSearch(search.trim());
    setAppliedPlanFilter(planFilter);
    setAppliedStatus(status);
    setAppliedCycle(cycle);
  }

  function resetFilters() {
    setSearch("");
    setPlanFilter("all");
    setStatus("all");
    setCycle("all");
    setAppliedSearch("");
    setAppliedPlanFilter("all");
    setAppliedStatus("all");
    setAppliedCycle("all");
  }

  const filtersDirty =
    search.trim() !== appliedSearch ||
    planFilter !== appliedPlanFilter ||
    status !== appliedStatus ||
    cycle !== appliedCycle;

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

  function handleUnassign(row: SubscriptionRecord) {
    setConfirmAction({ type: "unassign", row });
  }

  function handleCancelBilling(row: SubscriptionRecord) {
    setConfirmAction({ type: "cancel-billing", row });
  }

  /** Row-level Extend Trial (SubscriptionCellAction) -- only ever called
   * for a row already known to be status==='trial' (the dropdown item is
   * conditional on that), so this applies unconditionally rather than
   * re-filtering a list of one. */
  async function handleExtendTrial(row: SubscriptionRecord) {
    const base = row.renewal_date ? new Date(row.renewal_date) : new Date();
    base.setDate(base.getDate() + 14);
    await assign(row.hospital_id, {
      plan_id: row.plan_id as number,
      billing_cycle: row.billing_cycle ?? "monthly",
      status: "trial",
      payment_status: row.payment_status ?? "pending",
      renewal_date: base.toISOString().slice(0, 10),
    });
    toast.success(`Trial extended for ${row.hospital_name}`);
  }

  /** Row-level Cancel Subscription -- reuses the same confirm-dialog flow
   * (and runConfirmedAction's billed-vs-manual split below) the old bulk
   * "Cancel Subscription" Quick Action used, just with a single-row list. */
  function handleCancelSubscription(row: SubscriptionRecord) {
    setConfirmAction({ type: "bulk-cancel", rows: [row] });
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
      <div className="mb-space-5 gap-space-3 flex flex-col items-start justify-between lg:flex-row lg:items-center">
        <div>
          <h1 className="text-display">Subscriptions</h1>
          <p className="text-ink-600 text-[13px]">
            Manage hospital subscription records, renewals, and billing across CareConnect.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExportOpen(true)}
          className="border-line text-ink-700 gap-space-2 px-space-3 hover:bg-paper flex h-9 items-center rounded-md border text-[12.5px] font-semibold"
        >
          <Download size={14} /> Export
        </button>
      </div>

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <StatTileGrid cols={5} className="mb-space-4">
        <StatTile label="Active Subscriptions" value={stats.active} icon={Users} />
        <StatTile label="Trials" value={stats.trials} icon={FlaskConical} tint="brand" />
        <StatTile
          label="Renewals This Month"
          value={stats.renewalsThisMonth}
          icon={Clock}
          tint="clay"
        />
        <StatTile label="Churned Accounts" value={stats.churned} icon={Pause} tint="error" />
        <StatTile
          label="Avg. Subscription Value"
          value={Math.round(stats.avgValue)}
          prefix="₹"
          icon={BarChart3}
        />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4 mb-space-4">
            <div className="gap-space-3 flex flex-wrap items-center">
              <div className="relative min-w-50 flex-1">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by hospital name…"
                  className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13px]"
                />
              </div>
              <FilterSelect
                value={planFilter}
                onChange={setPlanFilter}
                options={plans.map((p) => ({ value: String(p.id), label: p.name }))}
                allLabel="All Plans"
              />
              <FilterSelect
                value={status}
                onChange={setStatus}
                options={STATUS_OPTIONS}
                allLabel="All Statuses"
              />
              <FilterSelect
                value={cycle}
                onChange={setCycle}
                options={CYCLE_OPTIONS}
                allLabel="All Cycles"
              />
              <FilterActions
                onApply={applyFilters}
                onReset={resetFilters}
                showReset={
                  filtersDirty ||
                  !!appliedSearch ||
                  appliedPlanFilter !== "all" ||
                  appliedStatus !== "all" ||
                  appliedCycle !== "all"
                }
                disabled={!filtersDirty}
              />
            </div>
          </Card>

          <ExportDialog
            open={exportOpen}
            onOpenChange={setExportOpen}
            title="Hospital Subscriptions"
            exportMutation={exportMutation}
            history={exportHistory}
            historyPage={exportHistoryPage}
            onHistoryPageChange={setExportHistoryPage}
            showDateRange={false}
          />

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
                  onEdit: setEditing,
                  onExtendTrial: handleExtendTrial,
                  onCancelSubscription: handleCancelSubscription,
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
                ["Total Annual Contract Value (ACV)", formatINR(Math.round(stats.totalACV))],
                ["Average Subscription Value", formatINR(Math.round(stats.avgValue))],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-ink-400">{label}</span>
                  <span className="text-ink-900 font-semibold">{value}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <AuditActivityTable
        entries={subscriptionActivity}
        isLoading={!auditEntries}
        title="Recent Subscription Activities"
        subtitle="Recent changes to hospital subscriptions across all tenants."
        emptyMessage="No subscription changes yet."
        showActorLevelFilter={true}
        showHospitalColumn={true}
      />

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
                ? confirmAction.rows.length === 1
                  ? `Cancel ${confirmAction.rows[0].hospital_name}'s subscription?`
                  : `Cancel ${confirmAction.rows.length} subscriptions? Hospitals on live Razorpay billing will have their real subscription cancelled; others are marked cancelled directly.`
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
