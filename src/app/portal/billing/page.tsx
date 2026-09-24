"use client";

import { useMemo, useState } from "react";
import { CalendarDays, IndianRupee, Receipt, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { formatHeaderDate } from "@/lib/formatDate";
import { usePayments, type PaymentRow } from "@/hooks/usePayments";
import {
  createBillingColumns,
  PAYMENT_METHOD_LABELS,
  PAYMENT_STATUS_LABELS,
} from "./_components/billing-columns";
import { PaymentDetailPanel } from "./_components/PaymentDetailPanel";

const STATUS_OPTIONS = Object.entries(PAYMENT_STATUS_LABELS).map(([value, label]) => ({
  value,
  label,
}));
const METHOD_OPTIONS = Object.entries(PAYMENT_METHOD_LABELS).map(([value, label]) => ({
  value,
  label,
}));

function isSameDay(iso: string, ref: Date): boolean {
  const d = new Date(iso);
  return (
    d.getFullYear() === ref.getFullYear() &&
    d.getMonth() === ref.getMonth() &&
    d.getDate() === ref.getDate()
  );
}

export default function BillingPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("billing", "view");

  const { payments, error } = usePayments(canView);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [methodFilter, setMethodFilter] = useState("all");

  const today = useMemo(() => new Date(), []);

  const rows: PaymentRow[] = useMemo(() => payments || [], [payments]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return rows.filter((p) => {
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      if (methodFilter !== "all" && p.method !== methodFilter) return false;
      if (!q) return true;
      return (
        (p.patient_name || "").toLowerCase().includes(q) ||
        (p.patient_phone || "").includes(q) ||
        (p.reference_id || "").toLowerCase().includes(q)
      );
    });
  }, [rows, searchQuery, statusFilter, methodFilter]);

  // Auto-selects the first (visible) row when nothing's been explicitly
  // clicked yet -- same convention as the Staff/Doctors pages' own detail
  // panels, so the detail panel never starts on an empty "select someone"
  // state while the ledger has at least one row to show.
  const selected = rows.find((p) => p.id === selectedId) || filteredRows[0] || null;

  const paidRows = useMemo(() => rows.filter((p) => p.status === "paid"), [rows]);
  const totalCollected = useMemo(
    () => paidRows.reduce((sum, p) => sum + p.amount, 0),
    [paidRows],
  );
  const todaysCollection = useMemo(
    () =>
      paidRows
        .filter((p) => p.paid_at && isSameDay(p.paid_at, today))
        .reduce((sum, p) => sum + p.amount, 0),
    [paidRows, today],
  );
  const pendingCount = useMemo(
    () => rows.filter((p) => p.status === "pending").length,
    [rows],
  );

  return (
    <PortalShell hospital={hospital} active="billing">
      <PageHeader title="Billing" description={formatHeaderDate(today)} />

      {!ready || !canView ? (
        !ready ? null : (
          <p className="text-ink-400 text-[13px]">You don&apos;t have access to Billing.</p>
        )
      ) : (
        <>
          {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

          <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Total Collected"
              value={payments ? totalCollected : null}
              deltaPct={null}
              hint="All paid transactions"
              icon={IndianRupee}
              prefix="₹"
            />
            <StatTile
              label="Today's Collection"
              value={payments ? todaysCollection : null}
              deltaPct={null}
              hint="Paid today"
              icon={CalendarDays}
              prefix="₹"
              tint="clay"
            />
            <StatTile
              label="Total Transactions"
              value={payments ? payments.length : null}
              deltaPct={null}
              hint="Live count"
              icon={Receipt}
            />
            <StatTile
              label="Pending"
              value={payments ? pendingCount : null}
              deltaPct={null}
              hint="Awaiting payment"
              icon={TrendingUp}
              tint="clay"
            />
          </div>

          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Card className="p-space-4">
                <div className="mb-space-3 gap-space-3 flex flex-wrap items-start justify-between">
                  <div>
                    <h3 className="text-label text-ink-900 font-bold">Transactions</h3>
                    <p className="text-hint mt-space-1">
                      Every payment attempt across appointments, newest first.
                    </p>
                  </div>
                </div>

                <div className="mb-space-3 gap-space-3 flex flex-wrap items-center">
                  <div className="relative min-w-50 flex-1">
                    <input
                      type="text"
                      placeholder="Search by patient, phone or reference…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="border-line bg-card px-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                    />
                  </div>
                  <FilterSelect
                    value={statusFilter}
                    onChange={setStatusFilter}
                    allLabel="All Status"
                    options={STATUS_OPTIONS}
                  />
                  <FilterSelect
                    value={methodFilter}
                    onChange={setMethodFilter}
                    allLabel="All Methods"
                    options={METHOD_OPTIONS}
                  />
                </div>

                <DataTable
                  columns={createBillingColumns({
                    onSelect: (p) => setSelectedId(p.id),
                  })}
                  data={filteredRows}
                  getRowId={(p) => String(p.id)}
                  onRowClick={(p) => setSelectedId(p.id)}
                  rowClassName={(p) => (p.id === selected?.id ? "bg-brand-50" : "")}
                  pageSize={10}
                  pageSizeOptions={[10, 25, 50]}
                  loading={!payments}
                  emptyMessage={
                    payments && payments.length > 0
                      ? "No transactions match your search/filters."
                      : "No transactions yet."
                  }
                />
              </Card>
            </div>

            <div>
              <PaymentDetailPanel payment={selected} />
            </div>
          </div>
        </>
      )}
    </PortalShell>
  );
}
