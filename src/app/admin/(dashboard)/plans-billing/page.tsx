"use client";

import { useState } from "react";
import {
  AlertCircle,
  Banknote,
  Building2,
  Check,
  FileDown,
  FileText,
  PenLine,
  Plus,
  Receipt,
  Search,
  Sprout,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { ExportDialog } from "@/components/export/ExportDialog";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { adminFetch, adminFetchBlob } from "@/lib/adminAuth";
import { cn } from "@/lib/cn";
import { formatINR } from "@/lib/formatCurrency";
import { CAPABILITY_META } from "@/lib/hospitalCapabilities";
import { useCsvExport, useExportHistory } from "@/hooks/useExport";
import { useAdminBillingRecords } from "@/hooks/useAdminBillingRecords";
import { useAdminPlans, type Plan } from "@/hooks/useAdminPlans";
import { createBillingColumns } from "./_components/billing-columns";
import { PlanFormDialog } from "./_components/PlanFormDialog";

function PanelHeader({ title, subtitle }: { title: string; subtitle?: string; mock?: boolean }) {
  return (
    <div className="mb-space-3 gap-space-3 flex items-start justify-between">
      <div>
        <h3 className="text-label text-ink-900 font-bold">{title}</h3>
        {subtitle && <p className="text-hint mt-space-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function PlansBillingPage() {
  const [search, setSearch] = useState("");
  const {
    plans,
    allCapabilities,
    error,
    createPlan,
    updatePlan,
    toggleActive,
    deletePlan,
    creating,
    updating,
  } = useAdminPlans();
  const {
    records: billingRecords,
    stats: billingStats,
    error: billingError,
  } = useAdminBillingRecords();
  const [formOpen, setFormOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportHistoryPage, setExportHistoryPage] = useState(1);

  const exportMutation = useCsvExport(
    adminFetchBlob,
    "/api/admin/billing-records/export",
    "subscription-billing-records.csv",
  );
  const exportHistory = useExportHistory(
    adminFetch,
    "/api/admin/exports/history",
    "SUBSCRIPTION_BILLING_RECORDS",
    exportHistoryPage,
  );

  const filteredRecords = (billingRecords ?? []).filter(
    (r) =>
      !search ||
      r.hospital_name.toLowerCase().includes(search.toLowerCase()) ||
      (r.razorpay_payment_id ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  function openCreate() {
    setEditingPlan(null);
    setFormOpen(true);
  }

  function openEdit(plan: Plan) {
    setEditingPlan(plan);
    setFormOpen(true);
  }

  async function handleDelete(plan: Plan) {
    if (!window.confirm(`Delete ${plan.name}? This can't be undone.`)) return;
    await deletePlan(plan.id, plan.name);
  }

  return (
    <div>
      <div className="mb-space-5 gap-space-3 flex flex-wrap items-start justify-between">
        <div>
          <h1 className="text-display">Plans &amp; Billing</h1>
          <p className="text-ink-600 text-[13px]">
            Manage pricing plans, billing operations and monitor revenue across all hospitals.
          </p>
        </div>
      </div>

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile
          label="Total Revenue"
          value={formatINR(billingStats?.total_revenue ?? 0)}
          icon={Banknote}
        />
        <StatTile
          label="Invoices Issued"
          value={billingStats?.invoices_issued ?? 0}
          icon={FileText}
        />
        <StatTile
          label="Failed Payments"
          value={billingStats?.failed_payments_count ?? 0}
          icon={AlertCircle}
          tint="error"
        />
        <StatTile
          label="Collections"
          value={formatINR(billingStats?.collections ?? 0)}
          icon={Receipt}
        />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4">
            <div className="mb-space-4 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">CareConnect Plans</h3>
                <p className="text-hint mt-space-0.5">
                  Flexible plans for hospitals of all sizes. Manage pricing, features and
                  availability.
                </p>
              </div>
              <button
                type="button"
                onClick={openCreate}
                className="bg-brand-600 hover:bg-brand-700 gap-space-1 px-space-3 flex h-8 shrink-0 items-center rounded-md text-[12.5px] font-semibold text-white"
              >
                <Plus size={13} /> New Plan
              </button>
            </div>

            {error && <p className="mb-space-3 text-error text-[12.5px]">{error}</p>}

            {!plans ? (
              <p className="text-ink-400 text-[13px]">Loading…</p>
            ) : plans.length === 0 ? (
              <p className="text-ink-400 text-[13px]">No plans yet — create one to get started.</p>
            ) : (
              <div className="gap-space-4 grid grid-cols-1 md:grid-cols-3">
                {plans.map((plan) => {
                  const Icon = plan.sort_order === 0 ? Sprout : Building2;
                  const annualPrice =
                    plan.price_monthly * 12 * (1 - plan.annual_discount_pct / 100);
                  return (
                    <div
                      key={plan.id}
                      className={cn(
                        "border-line p-space-4 relative flex flex-col rounded-lg border",
                        plan.is_popular && "border-brand-300 shadow-[var(--shadow-md)]",
                        !plan.is_active && "opacity-60",
                      )}
                    >
                      {plan.is_popular && (
                        <span className="bg-brand-600 px-space-3 right-space-3 absolute top-0 -translate-y-1/2 rounded-full py-1 text-[10.5px] font-bold tracking-wide text-white uppercase">
                          Most Popular
                        </span>
                      )}
                      <div className="mb-space-3 flex items-start justify-between">
                        <span className="bg-brand-50 text-brand-600 flex h-10 w-10 items-center justify-center rounded-full">
                          <Icon size={20} />
                        </span>
                        <div className="gap-space-1 flex items-center">
                          <Badge tone={plan.is_active ? "success" : "neutral"}>
                            {plan.is_active ? "Active" : "Inactive"}
                          </Badge>
                          <button
                            type="button"
                            onClick={() => handleDelete(plan)}
                            aria-label={`Delete ${plan.name}`}
                            className="text-ink-400 hover:bg-paper hover:text-error flex h-7 w-7 items-center justify-center rounded-md"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                      <h4 className="text-ink-900 text-[15px] font-bold">{plan.name}</h4>
                      <p className="text-hint mb-space-3">{plan.description}</p>
                      <div className="mb-space-1">
                        <span className="text-ink-900 text-[26px] font-bold">
                          {formatINR(plan.price_monthly)}
                        </span>
                        <span className="text-ink-400 text-[12.5px]"> / month</span>
                      </div>
                      <div className="mb-space-4 gap-space-2 flex items-center">
                        <span className="text-ink-400 text-[12px]">
                          or {formatINR(annualPrice)} / year
                        </span>
                        {plan.annual_discount_pct > 0 && (
                          <Badge tone="success">Save {plan.annual_discount_pct}%</Badge>
                        )}
                      </div>
                      <ul className="space-y-space-2 mb-space-4 flex-1 text-[12.5px]">
                        {plan.capabilities.map((key) => (
                          <li key={key} className="gap-space-2 flex items-start">
                            <Check size={14} className="text-success mt-0.5 shrink-0" />
                            <span className="text-ink-700">
                              {CAPABILITY_META[key]?.label ?? key}
                            </span>
                          </li>
                        ))}
                        <li className="gap-space-2 flex items-start">
                          <Check size={14} className="text-success mt-0.5 shrink-0" />
                          <span className="text-ink-700">
                            {plan.max_users == null
                              ? "Unlimited Staff Users"
                              : `Up to ${plan.max_users} Staff Users`}
                          </span>
                        </li>
                        <li className="gap-space-2 flex items-start">
                          <Check size={14} className="text-success mt-0.5 shrink-0" />
                          <span className="text-ink-700">
                            {plan.max_bookings == null
                              ? "Unlimited Bookings"
                              : `Up to ${plan.max_bookings.toLocaleString("en-IN")} Bookings`}
                          </span>
                        </li>
                      </ul>
                      <div className="gap-space-2 grid grid-cols-2">
                        <button
                          type="button"
                          onClick={() => openEdit(plan)}
                          className={cn(
                            "gap-space-2 py-space-2 flex items-center justify-center rounded-md text-[12.5px] font-semibold transition-colors duration-150",
                            plan.is_popular
                              ? "bg-brand-600 hover:bg-brand-700 text-white"
                              : "border-line text-ink-700 hover:bg-paper border",
                          )}
                        >
                          <PenLine size={13} /> Edit Plan
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleActive(plan)}
                          className="border-line text-ink-700 py-space-2 hover:bg-paper flex items-center justify-center rounded-md border text-[12.5px] font-semibold transition-colors duration-150"
                        >
                          {plan.is_active ? "Turn Off" : "Turn On"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {formOpen && (
            <PlanFormDialog
              open={formOpen}
              onOpenChange={setFormOpen}
              plan={editingPlan}
              nextSortOrder={plans?.length ?? 0}
              allCapabilities={allCapabilities}
              onSubmit={(payload) =>
                editingPlan ? updatePlan(editingPlan.id, payload) : createPlan(payload)
              }
              saving={creating || updating}
            />
          )}

          <Card className="p-space-4 mt-space-4">
            <div className="mb-space-4 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">Recent Billing Records</h3>
                <p className="text-hint mt-space-0.5">
                  Real subscription charges across all hospitals.
                </p>
              </div>
              <div className="gap-space-2 flex items-center">
                <div className="relative">
                  <Search
                    size={14}
                    className="text-ink-400 absolute top-1/2 left-3 -translate-y-1/2"
                  />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search payment id, hospitals…"
                    className="border-line bg-card pr-space-3 text-ink-900 h-9 w-56 rounded-md border pl-9 text-[12.5px]"
                  />
                </div>
              </div>
            </div>
            {billingError && <p className="mb-space-3 text-error text-[12.5px]">{billingError}</p>}
            {!billingRecords ? (
              <p className="text-ink-400 text-[13px]">Loading…</p>
            ) : filteredRecords.length === 0 ? (
              <p className="text-ink-400 text-[13px]">
                No billing records yet — they appear here once a hospital starts real billing from
                its own portal.
              </p>
            ) : (
              <DataTable
                columns={createBillingColumns()}
                data={filteredRecords}
                getRowId={(row) => String(row.id)}
                pageSize={10}
              />
            )}
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <PanelHeader
              title="Quick Actions"
              subtitle="Common billing and plan management actions."
              mock
            />
            <QuickActionList
              size="sm"
              columns={1}
              actions={[
                { label: "Create Plan", icon: Plus, onClick: openCreate },
                {
                  label: "Export Billing Report",
                  icon: FileDown,
                  onClick: () => setExportOpen(true),
                },
              ]}
            />
          </Card>

          <ExportDialog
            open={exportOpen}
            onOpenChange={setExportOpen}
            title="Subscription Billing Records"
            exportMutation={exportMutation}
            history={exportHistory}
            historyPage={exportHistoryPage}
            onHistoryPageChange={setExportHistoryPage}
            exportCap={10_000}
          />

          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-3 flex items-start justify-between">
              <h3 className="text-label text-ink-900 font-bold">Billing Summary</h3>
              <span className="text-ink-400 text-[11.5px] font-semibold">This Month</span>
            </div>
            <div className="space-y-space-2 text-[12.5px]">
              {[
                ["Total Invoiced", billingStats?.total_invoiced ?? 0, "text-ink-900"],
                ["Payments Received", billingStats?.collections_this_month ?? 0, "text-success"],
                ["Pending Payments", billingStats?.pending_payments ?? 0, "text-ink-900"],
                ["Failed Payments", billingStats?.failed_payments_amount ?? 0, "text-error"],
              ].map(([label, value, tone]) => (
                <div key={label as string} className="flex items-center justify-between">
                  <span className="text-ink-400">{label}</span>
                  <span className={cn("font-semibold", tone as string)}>
                    {formatINR(value as number)}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
