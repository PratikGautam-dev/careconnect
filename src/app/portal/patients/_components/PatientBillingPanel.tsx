"use client";

import { useState } from "react";
import { FileText, IndianRupee, Pill, Plus, Stethoscope, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { Textarea } from "@/components/ui/Input";
import { StatTile } from "@/components/portal/StatTile";
import { PatientStatTileRow } from "./PatientStatTileRow";
import { usePermission } from "@/lib/staffAuth";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import type { BillingRow } from "@/hooks/useBillingOverview";
import type { PatientBilling } from "@/hooks/usePatientDetail";
import {
  BILL_TYPE_LABELS, createBillingOverviewColumns, METHOD_LABELS, PAYMENT_STATUS_LABELS,
} from "../../billing/_components/billing-overview-columns";
import { BillDetailPanel } from "../../billing/_components/BillDetailPanel";

type Props = {
  patientId: number;
  billing: PatientBilling | null;
  billingNotes: string | null;
  onCollected: () => void;
  onSaveBillingNotes: (notes: string) => void;
  savingBillingNotes: boolean;
};

/** The patient detail page's "Billing" tab -- this one patient's own bills
 * across both domains (billing.transactions, already pre-filtered
 * server-side by db.get_patient_billing()), reusing the exact same
 * columns/detail-panel/collect-payment/refund flow as the hospital-wide
 * /portal/billing page -- a bill is a bill, whichever page it's viewed
 * from. Payment History below reads billing.payment_events -- every
 * attempt/collection event, not deduped to one row per bill the way the
 * table above is. */
export function PatientBillingPanel({ patientId, billing, billingNotes, onCollected, onSaveBillingNotes, savingBillingNotes }: Props) {
  const canWriteBilling = usePermission("billing", "write");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [billTypeFilter, setBillTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [methodFilter, setMethodFilter] = useState("all");
  const [notesDraft, setNotesDraft] = useState<string | null>(null);

  const allRows = billing?.transactions ?? [];
  const rows = allRows.filter((r) => {
    if (billTypeFilter !== "all" && r.bill_type !== billTypeFilter) return false;
    if (statusFilter !== "all" && r.payment_status !== statusFilter) return false;
    if (methodFilter !== "all" && r.method !== methodFilter) return false;
    return true;
  });
  const selected: BillingRow | null =
    allRows.find((r) => `${r.bill_type}-${r.id}` === selectedKey) || rows[0] || null;

  const notesValue = notesDraft !== null ? notesDraft : billingNotes || "";

  return (
    <>
      <PatientStatTileRow>
        <StatTile label="Total Billed" value={billing ? billing.stats.total_amount : null} icon={IndianRupee} prefix="₹" />
        <StatTile label="Total Paid" value={billing ? billing.stats.total_paid : null} icon={Wallet} prefix="₹" tint="success" />
        <StatTile label="Pending" value={billing ? billing.stats.pending_dues : null} icon={FileText} prefix="₹" tint="clay" />
        <StatTile label="Appointment Bills" value={billing ? billing.stats.appointment_bills_total : null} icon={Stethoscope} prefix="₹" tint="clay" />
        <StatTile label="Pharmacy Bills" value={billing ? billing.stats.pharmacy_bills_total : null} icon={Pill} prefix="₹" />
      </PatientStatTileRow>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-space-4">
          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-2 flex flex-wrap items-center justify-between">
              <h3 className="text-label text-ink-900 font-bold">Bills & Payments ({allRows.length})</h3>
              <div className="gap-space-2 flex flex-wrap items-center">
                <CreateBillButton />
                <Button size="md" variant="secondary" href={`/portal/patients/${patientId}/statement`}>
                  <FileText size={14} /> Generate Patient Statement
                </Button>
              </div>
            </div>

            <div className="mb-space-3 gap-space-2 flex flex-wrap items-center">
              <FilterSelect value={billTypeFilter} onChange={setBillTypeFilter} allLabel="All Bill Types" options={Object.entries(BILL_TYPE_LABELS).map(([value, label]) => ({ value, label }))} />
              <FilterSelect value={statusFilter} onChange={setStatusFilter} allLabel="All Payment Status" options={Object.entries(PAYMENT_STATUS_LABELS).map(([value, label]) => ({ value, label }))} />
              <FilterSelect value={methodFilter} onChange={setMethodFilter} allLabel="All Payment Modes" options={Object.entries(METHOD_LABELS).map(([value, label]) => ({ value, label }))} />
            </div>

            {!billing ? (
              <p className="text-hint py-space-4 text-center text-[13px]">Loading…</p>
            ) : rows.length === 0 ? (
              <p className="text-hint py-space-4 text-center text-[13px]">No bills match.</p>
            ) : (
              <DataTable
                columns={createBillingOverviewColumns((r) => setSelectedKey(`${r.bill_type}-${r.id}`))}
                data={rows}
                getRowId={(r) => `${r.bill_type}-${r.id}`}
                onRowClick={(r) => setSelectedKey(`${r.bill_type}-${r.id}`)}
                rowClassName={(r) => (selected && r.bill_type === selected.bill_type && r.id === selected.id ? "bg-brand-50" : "")}
                pageSize={10}
              />
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Payment History (This Patient)</h3>
            {!billing || billing.payment_events.length === 0 ? (
              <p className="text-hint py-space-3 text-center text-[12.5px]">No payment events yet.</p>
            ) : (
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-hint text-left">
                    <th className="py-space-2 font-semibold">Transaction ID</th>
                    <th className="py-space-2 font-semibold">Date & Time</th>
                    <th className="py-space-2 font-semibold">Bill No.</th>
                    <th className="py-space-2 font-semibold">Payment Mode</th>
                    <th className="py-space-2 text-right font-semibold">Amount</th>
                    <th className="py-space-2 text-right font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-line divide-y">
                  {billing.payment_events.map((e) => (
                    <tr key={e.transaction_id}>
                      <td className="py-space-2 text-brand-700 font-mono font-semibold">{e.transaction_id}</td>
                      <td className="py-space-2 text-ink-600">{formatShortDateTime(e.date)}</td>
                      <td className="py-space-2 text-ink-600 font-mono">{e.bill_no}</td>
                      <td className="py-space-2 text-ink-600">{e.method ? (METHOD_LABELS[e.method] ?? e.method) : "—"}</td>
                      <td className="py-space-2 text-ink-900 text-right font-semibold">{formatINR(e.amount)}</td>
                      <td className="py-space-2 text-right"><Badge tone={e.status === "paid" ? "success" : e.status === "failed" || e.status === "expired" || e.status === "cancelled" ? "neutral" : "clay"}>{PAYMENT_STATUS_LABELS[e.status] ?? e.status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Payment Notes</h3>
            <Textarea
              value={notesValue}
              onChange={(e) => setNotesDraft(e.target.value)}
              rows={3}
              placeholder="Add notes about payments, discounts, refunds, or other billing information…"
            />
            <div className="mt-space-2 flex justify-end">
              <Button size="md" disabled={savingBillingNotes || notesDraft === null} onClick={() => { onSaveBillingNotes(notesDraft ?? ""); setNotesDraft(null); }}>
                {savingBillingNotes ? "Saving…" : "Save Notes"}
              </Button>
            </div>
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Billing Summary</h3>
            {!billing ? (
              <p className="text-hint text-[12.5px]">Loading…</p>
            ) : (
              <dl className="space-y-space-2 text-[12.5px]">
                <div className="flex justify-between"><dt className="text-ink-600">Appointment Charges</dt><dd className="text-ink-900 font-semibold">{formatINR(billing.stats.appointment_bills_total)}</dd></div>
                <div className="flex justify-between"><dt className="text-ink-600">Pharmacy Charges</dt><dd className="text-ink-900 font-semibold">{formatINR(billing.stats.pharmacy_bills_total)}</dd></div>
                <div className="border-line flex justify-between border-t pt-space-2 font-bold"><dt className="text-ink-700">Total Amount</dt><dd className="text-ink-900">{formatINR(billing.stats.total_amount)}</dd></div>
                <div className="flex justify-between"><dt className="text-ink-600">Paid Amount</dt><dd className="text-success font-semibold">{formatINR(billing.stats.total_paid)}</dd></div>
                <div className="flex justify-between"><dt className="text-ink-600">Outstanding Balance</dt><dd className="text-clay-700 font-semibold">{formatINR(billing.stats.pending_dues)}</dd></div>
              </dl>
            )}
          </Card>

          <BillDetailPanel bill={selected} canWrite={canWriteBilling} onCollected={onCollected} />
        </div>
      </div>
    </>
  );
}

/** Overview tab's own small "+ Create Bill" affordance -- pharmacy OTC
 * billing is the only staff-initiated "create a bill right now" flow this
 * product has (appointment bills are generated by the booking flow
 * itself, never created freestanding) -- same single destination the
 * hospital-wide Billing page's own header action points to. */
export function CreateBillButton() {
  const canWriteBilling = usePermission("billing", "write");
  if (!canWriteBilling) return null;
  return (
    <Button href="/portal/pharmacy-billing" size="md">
      <Plus size={14} /> Create Bill
    </Button>
  );
}
