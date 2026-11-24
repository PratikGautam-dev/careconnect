"use client";

import { useState } from "react";
import {
  AlertTriangle, ArrowDownLeft, ArrowUpRight, Database, Eye, Printer, RotateCcw, Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { Input } from "@/components/ui/Input";
import { StatTile } from "@/components/portal/StatTile";
import { PatientStatTileRow } from "./PatientStatTileRow";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { useCollectCashPayment } from "@/hooks/useAppointmentDetail";
import { useRefunds } from "@/hooks/useRefunds";
import { usePermission } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import type { PaymentEvent, PatientBilling } from "@/hooks/usePatientDetail";

const TYPE_LABELS: Record<string, string> = { payment: "Payment", refund: "Refund" };
const RELATED_TO_LABELS: Record<string, string> = { appointment: "Appointment", pharmacy: "Pharmacy" };
const STATUS_LABELS: Record<string, string> = {
  paid: "Success", pending: "Pending", failed: "Failed", expired: "Expired",
  pay_at_hospital: "Pay at Hospital", cancelled: "Cancelled", refunded: "Refunded",
  partially_paid: "Partially Paid",
};
const STATUS_TONES: Record<string, "success" | "clay" | "neutral" | "brand"> = {
  paid: "success", pending: "clay", failed: "neutral", expired: "neutral",
  pay_at_hospital: "clay", cancelled: "neutral", refunded: "brand", partially_paid: "clay",
};
const DATE_RANGE_OPTIONS = [
  { value: "7", label: "Last 7 Days" },
  { value: "30", label: "Last 30 Days" },
  { value: "90", label: "Last 90 Days" },
];

type Props = {
  patientId: number;
  billing: PatientBilling | null;
  billingNotes: string | null;
  onChanged: () => void;
  onSaveBillingNotes: (notes: string) => void;
  savingBillingNotes: boolean;
};

/** Patient Details page's "Transactions" tab -- every payment attempt,
 * pharmacy collection event, and refund event for this patient
 * (billing.payment_events, see db/repositories/billing_overview.py's
 * _payment_event_row()/_refund_event_row()), unlike the Billing tab's
 * one-row-per-invoice shape. "Retry" reuses the same collect-cash action
 * staff already use elsewhere -- there's no separate online-retry
 * mechanism (that's patient-initiated); "Process Refund" reuses the real
 * refund-approval pipeline, scoped to the selected transaction's
 * appointment. */
export function PatientTransactionsPanel({ patientId, billing, billingNotes, onChanged, onSaveBillingNotes, savingBillingNotes }: Props) {
  const canWriteBilling = usePermission("billing", "write");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateRange, setDateRange] = useState("30");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notesDraft, setNotesDraft] = useState<string | null>(null);

  const collectCash = useCollectCashPayment();
  const allEvents = billing?.payment_events ?? [];

  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - Number(dateRange));
  const filtered = allEvents.filter((e) => {
    if (typeFilter !== "all" && e.transaction_type !== typeFilter) return false;
    if (statusFilter !== "all" && e.status !== statusFilter) return false;
    if (new Date(e.date) < cutoff) return false;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      if (!e.transaction_id.toLowerCase().includes(q) && !e.bill_no.toLowerCase().includes(q) && !(e.gateway_ref || "").toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const selected = allEvents.find((e) => e.transaction_id === selectedId) || filtered[0] || null;

  const { refunds, approve: approveRefund, approvingId } = useRefunds(
    !!selected && selected.transaction_type === "refund", "", selected?.appointment_id ?? undefined,
  );
  const latestRefund = refunds.find((r) => `TRX-RFD-${r.id}` === selected?.transaction_id);

  const notesValue = notesDraft !== null ? notesDraft : billingNotes || "";

  async function handleRetry(e: PaymentEvent) {
    if (!e.appointment_id) return;
    try {
      await collectCash.mutateAsync({ appointmentId: String(e.appointment_id), amount: e.amount, reference: `Retry of ${e.transaction_id}` });
      toast.success("Payment collected");
      onChanged();
    } catch (err) {
      toast.error("Couldn't collect payment", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function handleProcessRefund() {
    if (!latestRefund) return;
    approveRefund(latestRefund.id);
    onChanged();
  }

  return (
    <>
      <PatientStatTileRow>
        <StatTile label="Total Transactions" value={billing ? billing.stats.total_transactions : null} icon={Database} />
        <StatTile label="Total Credits" value={billing ? billing.stats.total_credits : null} icon={Wallet} prefix="₹" tint="success" />
        <StatTile label="Total Debits / Refunds" value={billing ? billing.stats.total_debits : null} icon={ArrowDownLeft} prefix="₹" tint="clay" />
        <StatTile label="Net Amount" value={billing ? billing.stats.net_amount : null} icon={ArrowUpRight} prefix="₹" />
        <StatTile label="Failed / Pending" value={billing ? billing.stats.failed_pending_count : null} icon={AlertTriangle} tint="error" />
      </PatientStatTileRow>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2 min-w-0">
          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-2 flex flex-wrap items-center justify-between">
              <h3 className="text-label text-ink-900 font-bold">Transactions (This Patient)</h3>
              <Button size="md" variant="secondary" href={`/portal/patients/${patientId}/statement`}>
                <Printer size={14} /> Download Statement
              </Button>
            </div>

            <div className="mb-space-3 gap-space-2 flex flex-wrap items-center">
              <Input
                placeholder="Search by Transaction ID, Bill No., or Gateway…"
                value={search} onChange={(e) => setSearch(e.target.value)} className="h-9 min-w-50 flex-1"
              />
              <FilterSelect value={typeFilter} onChange={setTypeFilter} allLabel="All Types" options={Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }))} />
              <FilterSelect value={statusFilter} onChange={setStatusFilter} allLabel="All Status" options={Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))} />
              <FilterSelect value={dateRange} onChange={setDateRange} allLabel="All Time" options={DATE_RANGE_OPTIONS} />
            </div>

            {!billing ? (
              <p className="text-hint py-space-4 text-center text-[13px]">Loading…</p>
            ) : filtered.length === 0 ? (
              <p className="text-hint py-space-4 text-center text-[13px]">No transactions match.</p>
            ) : (
              <DataTable
                columns={[
                  { id: "transaction_id", header: "Transaction ID", cell: ({ row }: { row: { original: PaymentEvent } }) => (
                    <button type="button" onClick={() => setSelectedId(row.original.transaction_id)} className="text-brand-700 font-mono text-[12px] font-semibold hover:underline">
                      {row.original.transaction_id}
                    </button>
                  ) },
                  { id: "date", header: "Date & Time", cell: ({ row }: { row: { original: PaymentEvent } }) => <span className="text-ink-600">{formatShortDateTime(row.original.date)}</span> },
                  { id: "related_to", header: "Related To", cell: ({ row }: { row: { original: PaymentEvent } }) => <Badge tone="brand">{RELATED_TO_LABELS[row.original.related_to]}</Badge> },
                  { id: "bill_no", header: "Bill No. / Ref.", cell: ({ row }: { row: { original: PaymentEvent } }) => <span className="text-ink-600 font-mono">{row.original.bill_no}</span> },
                  { id: "transaction_type", header: "Type", cell: ({ row }: { row: { original: PaymentEvent } }) => <Badge tone={row.original.transaction_type === "refund" ? "clay" : "neutral"}>{TYPE_LABELS[row.original.transaction_type]}</Badge> },
                  { id: "method", header: "Mode", cell: ({ row }: { row: { original: PaymentEvent } }) => <span className="text-ink-600 capitalize">{row.original.method || "—"}</span> },
                  { id: "amount", header: "Amount", cell: ({ row }: { row: { original: PaymentEvent } }) => <span className="text-ink-900 font-semibold">{formatINR(row.original.amount)}</span> },
                  { id: "status", header: "Status", cell: ({ row }: { row: { original: PaymentEvent } }) => <Badge tone={STATUS_TONES[row.original.status] ?? "neutral"}>{STATUS_LABELS[row.original.status] ?? row.original.status}</Badge> },
                  { id: "actions", header: "Actions", enableHiding: false, cell: ({ row }: { row: { original: PaymentEvent } }) => (
                    <div className="gap-space-1 flex items-center">
                      <Button size="md" variant="secondary" onClick={() => setSelectedId(row.original.transaction_id)}><Eye size={13} /> View</Button>
                      {canWriteBilling && row.original.status === "pending" && row.original.transaction_type === "payment" && (
                        <Button size="md" variant="secondary" disabled={collectCash.isPending} onClick={() => handleRetry(row.original)}>
                          <RotateCcw size={13} /> Retry
                        </Button>
                      )}
                    </div>
                  ) },
                ]}
                data={filtered}
                getRowId={(e: PaymentEvent) => e.transaction_id}
                onRowClick={(e: PaymentEvent) => setSelectedId(e.transaction_id)}
                rowClassName={(e: PaymentEvent) => (selected?.transaction_id === e.transaction_id ? "bg-brand-50" : "")}
                pageSize={10}
              />
            )}
          </Card>

          <Card className="p-space-4 mt-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Transaction Notes</h3>
            <p className="text-hint mb-space-3">Shared with the Billing tab&apos;s Payment Notes -- one note per patient.</p>
            <textarea
              value={notesValue}
              onChange={(e) => setNotesDraft(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="Add administrative notes related to payments, refunds, or reconciliation (e.g., retry attempts, patient request, refund reason, etc.)…"
              className="border-line bg-card px-space-3 py-space-2 text-ink-900 focus:border-brand-400 w-full rounded-md border text-[13px] outline-none"
            />
            <div className="mt-space-1 flex items-center justify-between">
              <span className="text-hint">{notesValue.length} / 500</span>
              <Button size="md" disabled={savingBillingNotes || notesDraft === null} onClick={() => { onSaveBillingNotes(notesDraft ?? ""); setNotesDraft(null); }}>
                {savingBillingNotes ? "Saving…" : "Save Notes"}
              </Button>
            </div>
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Selected Transaction Details</h3>
            {!selected ? (
              <p className="text-hint text-[12.5px]">No transaction selected.</p>
            ) : (
              <dl className="space-y-space-2 text-[12.5px]">
                <div className="flex justify-between"><dt className="text-hint">Transaction ID</dt><dd className="text-ink-900 font-mono font-semibold">{selected.transaction_id}</dd></div>
                <div className="flex justify-between"><dt className="text-hint">Bill No.</dt><dd className="text-ink-900 font-mono font-semibold">{selected.bill_no}</dd></div>
                <div className="flex justify-between"><dt className="text-hint">Related To</dt><dd className="text-ink-900 font-semibold">{RELATED_TO_LABELS[selected.related_to]}</dd></div>
                <div className="flex justify-between"><dt className="text-hint">Type</dt><dd className="text-ink-900 font-semibold">{TYPE_LABELS[selected.transaction_type]}</dd></div>
                <div className="flex justify-between"><dt className="text-hint">Mode</dt><dd className="text-ink-900 font-semibold capitalize">{selected.method || "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-hint">Date &amp; Time</dt><dd className="text-ink-900 font-semibold">{formatShortDateTime(selected.date)}</dd></div>
                <div className="flex justify-between"><dt className="text-hint">Amount</dt><dd className="text-ink-900 font-semibold">{formatINR(selected.amount)}</dd></div>
                <div className="flex justify-between"><dt className="text-hint">Status</dt><dd><Badge tone={STATUS_TONES[selected.status] ?? "neutral"}>{STATUS_LABELS[selected.status] ?? selected.status}</Badge></dd></div>
                <div className="flex justify-between"><dt className="text-hint">Gateway Ref.</dt><dd className="text-ink-900 font-semibold">{selected.gateway_ref || "—"}</dd></div>
                {selected.notes && <div className="flex justify-between"><dt className="text-hint">Notes</dt><dd className="text-ink-900 text-right font-semibold">{selected.notes}</dd></div>}
              </dl>
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Payment Breakdown</h3>
            {!billing ? (
              <p className="text-hint text-[12.5px]">Loading…</p>
            ) : (
              <>
                <dl className="space-y-space-2 text-[12.5px]">
                  <div className="flex justify-between"><dt className="text-ink-600">Appointment Payments</dt><dd className="text-ink-900 font-semibold">{formatINR(billing.stats.credits_appointment)}</dd></div>
                  <div className="flex justify-between"><dt className="text-ink-600">Pharmacy Payments</dt><dd className="text-ink-900 font-semibold">{formatINR(billing.stats.credits_pharmacy)}</dd></div>
                  <div className="flex justify-between"><dt className="text-ink-600">Refunds</dt><dd className="text-error font-semibold">- {formatINR(billing.stats.total_debits)}</dd></div>
                </dl>
                <div className="bg-success-tint mt-space-3 flex items-center justify-between rounded-md p-3">
                  <span className="text-success text-[12.5px] font-bold">Net Received</span>
                  <span className="text-success text-[13px] font-bold">{formatINR(billing.stats.net_amount)}</span>
                </div>
              </>
            )}
          </Card>

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Quick Actions</h3>
            <div className="gap-space-2 grid grid-cols-2">
              <Button size="md" variant="secondary" onClick={() => window.print()} disabled={!selected}>
                <Printer size={14} /> Print Receipt
              </Button>
              <Button size="md" variant="secondary" href={`/portal/patients/${patientId}/statement`}>
                <Printer size={14} /> Download Statement
              </Button>
              <Button
                size="md" variant="secondary"
                disabled={!selected || selected.status !== "pending" || selected.transaction_type !== "payment" || collectCash.isPending}
                onClick={() => selected && handleRetry(selected)}
              >
                <RotateCcw size={14} /> Retry Payment
              </Button>
              <Button
                size="md" variant="secondary"
                disabled={!canWriteBilling || !selected || selected.transaction_type !== "refund" || !latestRefund || latestRefund.status !== "pending_approval" || approvingId === latestRefund?.id}
                onClick={handleProcessRefund}
              >
                <RotateCcw size={14} /> Process Refund
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
