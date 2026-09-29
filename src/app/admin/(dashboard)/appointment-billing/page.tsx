"use client";

import { useState } from "react";
import { Banknote, Download, IndianRupee, RefreshCcw, Wallet2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { toast } from "@/lib/toast";
import {
  useAppointmentBillingByHospital,
  useAppointmentBillingRefundQueue,
  useAppointmentBillingStats,
  useAppointmentBillingTrend,
} from "@/hooks/useAppointmentBilling";
import { createHospitalBillingColumns } from "./_components/appointment-billing-columns";
import { createRefundQueueColumns, REFUND_STATUS_LABEL } from "./_components/refund-queue-columns";
import { HospitalCollectionsBarChart } from "./_components/HospitalCollectionsBarChart";
import { RevenueTrendChart } from "./_components/RevenueTrendChart";
import { StatSplitDonuts } from "./_components/StatSplitDonuts";

const REFUND_STATUS_OPTIONS = Object.entries(REFUND_STATUS_LABEL).map(([value, label]) => ({
  value,
  label,
}));

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function last30DaysFrom(): string {
  const d = new Date();
  d.setDate(d.getDate() - 29);
  return d.toISOString().slice(0, 10);
}

const hospitalColumns = createHospitalBillingColumns();
const refundQueueColumns = createRefundQueueColumns(true);

/** Super-admin "Appointment Billing" page -- reconciling patient-facing
 * Razorpay collections (payments.payment_for='appointment') across every
 * hospital: how much actually came in, how much is the platform's own GST/
 * platform-fee revenue vs. the hospital's own money, and -- since a
 * hospital can be on either the platform's own Razorpay account or its own
 * (hospital_payment_settings.payment_mode) -- who's currently holding
 * money that belongs to the other side. Read-only reporting only; refund
 * approve/reject stays in the hospital's own portal.
 *
 * Every section below (stats, charts, hospital table, refund queue) is
 * driven by its OWN independent hook/query (admin/appointment_billing_api.py's
 * five separate endpoints) -- a slow refund-queue fetch never blocks the
 * stat tiles from rendering, same "separate sections, don't wait on each
 * other" requirement the whole page was built around. */
function AppointmentBillingOverview() {
  const [dateFrom, setDateFrom] = useState(last30DaysFrom());
  const [dateTo, setDateTo] = useState(today());
  const [methodFilter, setMethodFilter] = useState("all");
  const [refundStatusFilter, setRefundStatusFilter] = useState("all");
  const [hospitalPage, setHospitalPage] = useState(1);
  const [refundPage, setRefundPage] = useState(1);

  const range = { dateFrom, dateTo };
  const { stats } = useAppointmentBillingStats(range);
  const { trend } = useAppointmentBillingTrend(range);
  const { rows: hospitalRows, total: hospitalTotal } = useAppointmentBillingByHospital(
    { ...range, method: methodFilter === "all" ? undefined : methodFilter },
    hospitalPage,
  );
  const { rows: refundRows, total: refundTotal } = useAppointmentBillingRefundQueue(
    { ...range, status: refundStatusFilter === "all" ? undefined : refundStatusFilter },
    refundPage,
  );

  function resetPages() {
    setHospitalPage(1);
    setRefundPage(1);
  }

  function updateDateFrom(value: string) {
    setDateFrom(value);
    resetPages();
  }

  function updateDateTo(value: string) {
    setDateTo(value);
    resetPages();
  }

  function resetToToday() {
    setDateFrom(today());
    setDateTo(today());
    resetPages();
  }

  return (
    <div>
      <div className="mb-space-5 gap-space-3 flex flex-col items-start justify-between lg:flex-row lg:items-center">
        <div>
          <h1 className="text-display">Appointment Billing</h1>
          <p className="text-ink-600 text-[13px]">
            Reconcile patient payments across every hospital -- what came in, what&apos;s the
            platform&apos;s own revenue, and what each side still owes the other.
          </p>
        </div>

        <div className="gap-space-2 flex flex-wrap items-center lg:justify-end">
          <div className="gap-space-2 flex items-center">
            <label className="text-ink-600 text-[12.5px] font-medium" htmlFor="ab-date-from">
              From
            </label>
            <input
              id="ab-date-from"
              type="date"
              value={dateFrom}
              max={dateTo}
              onChange={(e) => updateDateFrom(e.target.value)}
              className="border-line bg-card px-space-2 text-ink-900 h-9 rounded-md border text-[12.5px]"
            />
            <label className="text-ink-600 text-[12.5px] font-medium" htmlFor="ab-date-to">
              To
            </label>
            <input
              id="ab-date-to"
              type="date"
              value={dateTo}
              min={dateFrom}
              max={today()}
              onChange={(e) => updateDateTo(e.target.value)}
              className="border-line bg-card px-space-2 text-ink-900 h-9 rounded-md border text-[12.5px]"
            />
          </div>
          <button
            type="button"
            onClick={resetToToday}
            className="text-brand-600 text-[12.5px] font-semibold hover:underline"
          >
            Today
          </button>
          <FilterSelect
            value={methodFilter}
            onChange={(v) => {
              setMethodFilter(v);
              setHospitalPage(1);
            }}
            allLabel="All Payment Modes"
            options={[
              { value: "online", label: "Online" },
              { value: "pay_at_hospital", label: "Cash" },
            ]}
          />
          <button
            type="button"
            onClick={() => toast.success("Export coming soon")}
            className="border-line text-ink-600 hover:bg-canvas gap-space-1 px-space-3 flex h-9 items-center rounded-md border text-[12.5px] font-semibold"
          >
            <Download size={14} /> Export
          </button>
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

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <RevenueTrendChart data={trend} className="lg:col-span-2" />
        <StatSplitDonuts stats={stats} />
      </div>
      <div className="mb-space-4">
        <HospitalCollectionsBarChart rows={hospitalRows} />
      </div>

      <Card className="p-space-4 mb-space-4">
        <h3 className="text-label text-ink-900 mb-space-3 font-bold">Collections by Hospital</h3>
        <DataTable
          columns={hospitalColumns}
          data={hospitalRows ?? []}
          getRowId={(row) => String(row.hospital_id)}
          loading={!hospitalRows}
          emptyMessage="No collections in this range."
          pagination={{ page: hospitalPage, limit: 25, total: hospitalTotal }}
          onPageChange={setHospitalPage}
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

export default function AppointmentBillingPage() {
  return <AppointmentBillingOverview />;
}
