"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Download,
  IndianRupee,
  Pill,
  Plus,
  RotateCcw,
  Stethoscope,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { usePermission } from "@/lib/staffAuth";
import { formatHeaderDate } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { useBillingOverview, type BillingRow } from "@/hooks/useBillingOverview";
import {
  BILL_TYPE_LABELS,
  createBillingOverviewColumns,
  METHOD_LABELS,
  PAYMENT_STATUS_LABELS,
} from "./_components/billing-overview-columns";
import { BillDetailPanel } from "./_components/BillDetailPanel";

type Tab = "all" | "appointment" | "pharmacy" | "refunds" | "outstanding";

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All Transactions" },
  { id: "appointment", label: "Appointments" },
  { id: "pharmacy", label: "Pharmacy" },
  { id: "refunds", label: "Refunds" },
  { id: "outstanding", label: "Outstanding" },
];

const BILL_TYPE_OPTIONS = Object.entries(BILL_TYPE_LABELS).map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS = Object.entries(PAYMENT_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const METHOD_OPTIONS = Object.entries(METHOD_LABELS).map(([value, label]) => ({ value, label }));

export default function BillingPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("billing", "view");
  const canWrite = usePermission("billing", "write");

  const { overview, error, invalidate } = useBillingOverview(canView);

  const [tab, setTab] = useState<Tab>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [billTypeFilter, setBillTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [methodFilter, setMethodFilter] = useState("all");

  const today = useMemo(() => new Date(), []);
  const rows: BillingRow[] = useMemo(() => overview?.transactions ?? [], [overview]);

  const tabRows = useMemo(() => {
    switch (tab) {
      case "appointment":
        return rows.filter((r) => r.bill_type === "appointment");
      case "pharmacy":
        return rows.filter((r) => r.bill_type === "pharmacy");
      case "refunds":
        return rows.filter((r) => r.refund_amount > 0);
      case "outstanding":
        // Balance-due-based, matching the backend's own definition
        // (db/repositories/billing_overview.py) -- a "pay_at_hospital" bill
        // not yet collected owes real money too, a failed/expired/cancelled
        // attempt doesn't.
        return rows.filter(
          (r) =>
            r.amount - r.amount_paid > 0 &&
            !["failed", "expired", "cancelled"].includes(r.payment_status),
        );
      default:
        return rows;
    }
  }, [rows, tab]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return tabRows.filter((r) => {
      if (billTypeFilter !== "all" && r.bill_type !== billTypeFilter) return false;
      if (statusFilter !== "all" && r.payment_status !== statusFilter) return false;
      if (methodFilter !== "all" && r.method !== methodFilter) return false;
      if (!q) return true;
      return (
        (r.patient_name || "").toLowerCase().includes(q) ||
        (r.patient_phone || "").includes(q) ||
        r.invoice_ref.toLowerCase().includes(q)
      );
    });
  }, [tabRows, searchQuery, billTypeFilter, statusFilter, methodFilter]);

  const selected =
    rows.find((r) => `${r.bill_type}-${r.id}` === selectedKey) || filteredRows[0] || null;

  function handleCollected() {
    invalidate();
  }

  function handleExport() {
    const header = ["Invoice", "Bill Type", "Patient", "Amount", "Amount Paid", "Status", "Method", "Date"];
    const lines = filteredRows.map((r) => [
      r.invoice_ref, BILL_TYPE_LABELS[r.bill_type], r.patient_name, r.amount, r.amount_paid,
      PAYMENT_STATUS_LABELS[r.payment_status] ?? r.payment_status, r.method ?? "", r.date,
    ]);
    const csv = [header, ...lines]
      .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `billing-report-${today.toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <PortalShell hospital={hospital} active="billing">
      <PageHeader
        title="Billing & Payments"
        description={formatHeaderDate(today)}
        actions={
          ready && canView ? (
            <>
              <Button variant="secondary" onClick={handleExport} disabled={filteredRows.length === 0}>
                <Download size={16} /> Export Report
              </Button>
              {canWrite && (
                <Button href="/portal/pharmacy-billing">
                  <Plus size={16} /> Create Bill
                </Button>
              )}
            </>
          ) : null
        }
      />

      {!ready || !canView ? (
        !ready ? null : (
          <p className="text-ink-400 text-[13px]">You don&apos;t have access to Billing.</p>
        )
      ) : (
        <>
          {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

          <StatTileGrid cols={6} className="mb-space-4">
            <StatTile label="Total Billed" value={overview ? overview.stats.total_billed : null} icon={IndianRupee} prefix="₹" />
            <StatTile label="Appointment Bills" value={overview ? overview.stats.appointment_bills_total : null} icon={Stethoscope} prefix="₹" tint="clay" />
            <StatTile label="Pharmacy Bills" value={overview ? overview.stats.pharmacy_bills_total : null} icon={Pill} prefix="₹" />
            <StatTile label="Net Collected" value={overview ? overview.stats.net_collected : null} icon={Wallet} prefix="₹" tint="success" />
            <StatTile label="Outstanding" value={overview ? overview.stats.outstanding : null} icon={AlertTriangle} prefix="₹" tint="clay" />
            <StatTile label="Refunded" value={overview ? overview.stats.refunded : null} icon={RotateCcw} prefix="₹" tint="error" />
          </StatTileGrid>

          <div className="mb-space-4 gap-space-1 border-line bg-card p-space-1 flex w-fit flex-wrap rounded-lg border">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  "px-space-3 py-space-2 rounded-md text-[13px] font-semibold transition-colors duration-150",
                  tab === t.id
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-400 hover:text-ink-700 hover:bg-black/[0.04]",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Card className="p-space-4">
                <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
                  <div>
                    <h3 className="text-label text-ink-900 font-bold">Transactions & Invoices</h3>
                    <p className="text-hint mt-space-1">
                      Appointment and pharmacy bills in one ledger, newest first.
                    </p>
                  </div>
                </div>

                <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
                  <div className="relative min-w-50 flex-1">
                    <input
                      type="text"
                      placeholder="Search by patient, phone or invoice…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="border-line bg-card px-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                    />
                  </div>
                  <FilterSelect value={billTypeFilter} onChange={setBillTypeFilter} allLabel="All Bill Types" options={BILL_TYPE_OPTIONS} />
                  <FilterSelect value={statusFilter} onChange={setStatusFilter} allLabel="All Status" options={STATUS_OPTIONS} />
                  <FilterSelect value={methodFilter} onChange={setMethodFilter} allLabel="All Methods" options={METHOD_OPTIONS} />
                </div>

                <DataTable
                  columns={createBillingOverviewColumns((r) => setSelectedKey(`${r.bill_type}-${r.id}`))}
                  data={filteredRows}
                  getRowId={(r) => `${r.bill_type}-${r.id}`}
                  onRowClick={(r) => setSelectedKey(`${r.bill_type}-${r.id}`)}
                  rowClassName={(r) => (selected && r.bill_type === selected.bill_type && r.id === selected.id ? "bg-brand-50" : "")}
                  pageSize={10}
                  pageSizeOptions={[10, 25, 50]}
                  loading={!overview}
                  emptyMessage={rows.length > 0 ? "No bills match your search/filters." : "No bills yet."}
                />
              </Card>
            </div>

            <div>
              <BillDetailPanel bill={selected} canWrite={canWrite} onCollected={handleCollected} />
            </div>
          </div>

          <div className="mt-space-4 gap-space-4 grid grid-cols-1 lg:grid-cols-2">
            <Card className="p-space-4">
              <h3 className="text-label text-ink-900 mb-space-3 font-bold">Collection by Service</h3>
              {!overview ? (
                <p className="text-hint text-[12.5px]">Loading…</p>
              ) : (
                <div className="space-y-space-3">
                  {overview.collection_by_service.map((s) => {
                    const pct = s.billed > 0 ? Math.min(100, Math.round((s.collected / s.billed) * 100)) : 0;
                    return (
                      <div key={s.service}>
                        <div className="mb-space-1 flex items-center justify-between text-[12.5px]">
                          <span className="text-ink-700 font-semibold">{s.service}</span>
                          <span className="text-ink-600">{formatINR(s.collected)} / {formatINR(s.billed)}</span>
                        </div>
                        <div className="bg-paper h-2 w-full overflow-hidden rounded-full">
                          <div className="bg-brand-500 h-full rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            <Card className="p-space-4">
              <h3 className="text-label text-ink-900 mb-space-3 font-bold">Patient Clearance & Outstanding</h3>
              {!overview ? (
                <p className="text-hint text-[12.5px]">Loading…</p>
              ) : overview.patient_clearance.length === 0 ? (
                <p className="text-hint text-[12.5px]">No patients have an outstanding balance.</p>
              ) : (
                <div className="space-y-space-2">
                  {overview.patient_clearance.slice(0, 6).map((p) => (
                    <div key={p.patient_name} className="border-line flex items-center justify-between rounded-md border p-2.5">
                      <div>
                        <p className="text-ink-900 text-[12.5px] font-semibold">{p.patient_name}</p>
                        <p className="text-hint text-[11px]">
                          {p.appointment_balance > 0 && <>Appointment {formatINR(p.appointment_balance)}</>}
                          {p.appointment_balance > 0 && p.pharmacy_balance > 0 && " · "}
                          {p.pharmacy_balance > 0 && <>Pharmacy {formatINR(p.pharmacy_balance)}</>}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-clay-700 text-[13px] font-bold">{formatINR(p.total_due)}</p>
                        <p className="text-hint text-[10.5px]">Hold until cleared</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </PortalShell>
  );
}
