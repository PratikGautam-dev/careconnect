"use client";

import { use, useState } from "react";
import { Banknote, IndianRupee, RefreshCcw, Wallet2 } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { useTenants } from "@/hooks/useTenants";
import {
  useAppointmentBillingPayments,
  useAppointmentBillingRefundQueue,
  useAppointmentBillingStats,
  useAppointmentBillingTrend,
} from "@/hooks/useAppointmentBilling";
import { createAppointmentPaymentColumns } from "../_components/appointment-billing-columns";
import { createRefundQueueColumns, REFUND_STATUS_LABEL } from "../_components/refund-queue-columns";
import { RevenueTrendChart } from "../_components/RevenueTrendChart";

const REFUND_STATUS_OPTIONS = Object.entries(REFUND_STATUS_LABEL).map(([value, label]) => ({
  value,
  label,
}));
const PAYMENT_STATUS_OPTIONS = [
  { value: "paid", label: "Paid" },
  { value: "failed", label: "Failed" },
  { value: "pending", label: "Pending" },
  { value: "expired", label: "Expired" },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function last30DaysFrom(): string {
  const d = new Date();
  d.setDate(d.getDate() - 29);
  return d.toISOString().slice(0, 10);
}

const paymentColumns = createAppointmentPaymentColumns(false);
const refundQueueColumns = createRefundQueueColumns(false);

/** Appointment Billing's per-tenant detail page -- the "View →" drill-down
 * from the overview page's "Collections by Hospital" table (and its own
 * Refund Queue). Same page shape as the overview, all scoped to this one
 * hospital_id: its own stat tiles, its own money-trend chart, its full
 * payment list, and its own refund queue. No hospital-comparison chart or
 * platform-wide donuts here -- nothing to compare against on a
 * single-hospital page. */
function AppointmentBillingTenantDetail({ tenantId }: { tenantId: number }) {
  const { tenants } = useTenants();
  const hospital = tenants?.find((t) => t.id === tenantId) ?? null;

  const [dateFrom, setDateFrom] = useState(last30DaysFrom());
  const [dateTo, setDateTo] = useState(today());
  const [methodFilter, setMethodFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [refundStatusFilter, setRefundStatusFilter] = useState("all");
  const [paymentPage, setPaymentPage] = useState(1);
  const [refundPage, setRefundPage] = useState(1);

  const range = { dateFrom, dateTo, hospitalId: tenantId };
  const { stats } = useAppointmentBillingStats(range);
  const { trend } = useAppointmentBillingTrend(range);
  const { rows: paymentRows, total: paymentTotal } = useAppointmentBillingPayments(
    {
      ...range,
      method: methodFilter === "all" ? undefined : methodFilter,
      status: statusFilter === "all" ? undefined : statusFilter,
    },
    paymentPage,
  );
  const { rows: refundRows, total: refundTotal } = useAppointmentBillingRefundQueue(
    { ...range, status: refundStatusFilter === "all" ? undefined : refundStatusFilter },
    refundPage,
  );

  function resetPages() {
    setPaymentPage(1);
    setRefundPage(1);
  }

  return (
    <div>
      <Link
        href="/admin/appointment-billing"
        className="mb-space-4 text-brand-600 inline-block text-[13px] font-semibold hover:underline"
      >
        ← All hospitals
      </Link>

      <div className="mb-space-5 gap-space-3 flex flex-col items-start justify-between lg:flex-row lg:items-center">
        <div>
          <p className="text-eyebrow mb-space-1">Appointment Billing</p>
          <h1 className="text-display">{hospital ? hospital.name : "Loading…"}</h1>
        </div>

        <div className="gap-space-2 flex flex-wrap items-center lg:justify-end">
          <div className="gap-space-2 flex items-center">
            <label className="text-ink-600 text-[12.5px] font-medium" htmlFor="abd-date-from">
              From
            </label>
            <input
              id="abd-date-from"
              type="date"
              value={dateFrom}
              max={dateTo}
              onChange={(e) => {
                setDateFrom(e.target.value);
                resetPages();
              }}
              className="border-line bg-card px-space-2 text-ink-900 h-9 rounded-md border text-[12.5px]"
            />
            <label className="text-ink-600 text-[12.5px] font-medium" htmlFor="abd-date-to">
              To
            </label>
            <input
              id="abd-date-to"
              type="date"
              value={dateTo}
              min={dateFrom}
              max={today()}
              onChange={(e) => {
                setDateTo(e.target.value);
                resetPages();
              }}
              className="border-line bg-card px-space-2 text-ink-900 h-9 rounded-md border text-[12.5px]"
            />
          </div>
          <button
            type="button"
            onClick={() => {
              setDateFrom(today());
              setDateTo(today());
              resetPages();
            }}
            className="text-brand-600 text-[12.5px] font-semibold hover:underline"
          >
            Today
          </button>
          <FilterSelect
            value={methodFilter}
            onChange={(v) => {
              setMethodFilter(v);
              setPaymentPage(1);
            }}
            allLabel="All Payment Modes"
            options={[
              { value: "online", label: "Online" },
              { value: "pay_at_hospital", label: "Cash" },
            ]}
          />
          <FilterSelect
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v);
              setPaymentPage(1);
            }}
            allLabel="All Statuses"
            options={PAYMENT_STATUS_OPTIONS}
          />
        </div>
      </div>

      <StatTileGrid cols={5} className="mb-space-4">
        <StatTile
          label="Gross Collected"
          value={stats?.gross_collected ?? null}
          hint="In selected range"
          icon={IndianRupee}
          prefix="₹"
        />
        <StatTile
          label="Refunded"
          value={stats?.total_refunded ?? null}
          hint="Completed refunds only"
          icon={RefreshCcw}
          prefix="₹"
          tint="error"
        />
        <StatTile
          label="Net Actual"
          value={stats?.net_actual ?? null}
          hint="Gross − refunded"
          icon={Banknote}
          prefix="₹"
          tint="success"
        />
        <StatTile
          label="Online"
          value={stats?.online_collected ?? null}
          hint="In selected range"
          icon={Wallet2}
          prefix="₹"
        />
        <StatTile
          label="Cash"
          value={stats?.cash_collected ?? null}
          hint="Pay at hospital"
          icon={Wallet2}
          prefix="₹"
          tint="clay"
        />
      </StatTileGrid>

      <div className="mb-space-4">
        <RevenueTrendChart data={trend} />
      </div>

      <Card className="p-space-4 mb-space-4">
        <h3 className="text-label text-ink-900 mb-space-3 font-bold">Payments</h3>
        <DataTable
          columns={paymentColumns}
          data={paymentRows ?? []}
          getRowId={(row) => String(row.id)}
          loading={!paymentRows}
          emptyMessage="No payments in this range."
          pagination={{ page: paymentPage, limit: 25, total: paymentTotal }}
          onPageChange={setPaymentPage}
        />
      </Card>

      <Card className="p-space-4">
        <div className="mb-space-3 gap-space-3 flex flex-wrap items-center justify-between">
          <h3 className="text-label text-ink-900 font-bold">Refund Queue</h3>
          <FilterSelect
            value={refundStatusFilter}
            onChange={(v) => {
              setRefundStatusFilter(v);
              setRefundPage(1);
            }}
            allLabel="All Statuses"
            options={REFUND_STATUS_OPTIONS}
          />
        </div>
        <DataTable
          columns={refundQueueColumns}
          data={refundRows ?? []}
          getRowId={(row) => String(row.id)}
          loading={!refundRows}
          emptyMessage="No refund requests in this range."
          pagination={{ page: refundPage, limit: 25, total: refundTotal }}
          onPageChange={setRefundPage}
        />
      </Card>
    </div>
  );
}

export default function AppointmentBillingTenantPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  return <AppointmentBillingTenantDetail tenantId={Number(tenantId)} />;
}
