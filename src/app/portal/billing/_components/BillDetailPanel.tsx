"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { fetchPharmacySale } from "@/hooks/usePharmacyBilling";
import { useCollectCashPayment } from "@/hooks/useAppointmentDetail";
import { usePharmacyBilling } from "@/hooks/usePharmacyBilling";
import { useRefunds } from "@/hooks/useRefunds";
import { toast } from "@/lib/toast";
import type { BillingRow } from "@/hooks/useBillingOverview";
import { PAYMENT_STATUS_LABELS, PAYMENT_STATUS_TONES } from "./billing-overview-columns";

const REFUND_STATUS_LABELS: Record<string, string> = {
  pending_approval: "Pending Approval", approved: "Approved", processing: "Processing",
  completed: "Refunded", failed: "Failed", rejected: "Rejected",
};

type Props = {
  bill: BillingRow | null;
  canWrite: boolean;
  onCollected: () => void;
};

/** The combined ledger's own detail panel -- shows an appointment bill's
 * summary or a pharmacy bill's full line-item breakdown (fetched on
 * demand, same as the standalone /portal/pharmacy-billing/[id] page), and
 * collects payment through whichever domain's own existing route the
 * selected bill actually belongs to. */
export function BillDetailPanel({ bill, canWrite, onCollected }: Props) {
  const { data: pharmacySale } = useQuery({
    queryKey: ["portal-pharmacy-sale", bill?.bill_type === "pharmacy" ? bill.id : null],
    enabled: bill?.bill_type === "pharmacy",
    queryFn: () => fetchPharmacySale(bill!.id),
  });

  const collectCash = useCollectCashPayment();
  const { collectPayment: collectPharmacyPayment, collecting: collectingPharmacy } = usePharmacyBilling(false);
  const [method, setMethod] = useState("cash");
  const [amount, setAmount] = useState("");

  const isAppointmentBill = bill?.bill_type === "appointment";
  const { refunds, approve: approveRefund, approvingId } = useRefunds(
    isAppointmentBill, "", isAppointmentBill ? bill!.appointment_id ?? undefined : undefined,
  );
  const latestRefund = refunds[0] ?? null;

  const [prevBillKey, setPrevBillKey] = useState<string | null>(null);
  const billKey = bill ? `${bill.bill_type}-${bill.id}` : null;
  if (billKey !== prevBillKey) {
    setPrevBillKey(billKey);
    setAmount(bill ? String(bill.amount - bill.amount_paid) : "");
    setMethod("cash");
  }

  if (!bill) {
    return (
      <Card className="p-space-4">
        <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Bill & Payment Details</p>
        <p className="text-hint py-space-6 text-center text-[12.5px]">Select a bill to view its details.</p>
      </Card>
    );
  }

  const balanceDue = bill.amount - bill.amount_paid;
  const isSettled = balanceDue <= 0;

  async function handleCollect() {
    const amt = Number(amount);
    if (!amt || amt <= 0) return;
    try {
      if (bill!.bill_type === "appointment") {
        await collectCash.mutateAsync({ appointmentId: String(bill!.appointment_id), amount: amt, reference: "" });
        toast.success("Payment collected");
      } else {
        await collectPharmacyPayment(bill!.id, method, amt);
      }
      onCollected();
    } catch (err) {
      toast.error("Couldn't collect payment", err instanceof Error ? err.message : "Try again.");
    }
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <p className="text-ink-900 text-[13.5px] font-bold">Bill & Payment Details</p>
        <Badge tone={PAYMENT_STATUS_TONES[bill.payment_status] ?? "neutral"}>
          {PAYMENT_STATUS_LABELS[bill.payment_status] ?? bill.payment_status}
        </Badge>
      </div>

      <p className="text-ink-900 font-mono text-[14px] font-bold">{bill.invoice_ref}</p>
      <p className="text-hint text-[11.5px]">
        {bill.bill_type === "pharmacy" ? "Pharmacy Invoice" : "Appointment Invoice"}
        {bill.prescription_id && <> · Linked to prescription <span className="text-brand-700 font-semibold">RX-{bill.prescription_id}</span></>}
      </p>

      <div className="space-y-space-1 mt-space-3 text-[12.5px]">
        <p><span className="text-ink-400">Patient:</span> <span className="text-ink-900 font-medium">{bill.patient_name}</span></p>
        {bill.patient_phone && <p><span className="text-ink-400">Phone:</span> <span className="text-ink-900 font-medium">{bill.patient_phone}</span></p>}
        {bill.doctor_name && <p><span className="text-ink-400">Doctor:</span> <span className="text-ink-900 font-medium">{bill.doctor_name}</span></p>}
        <p><span className="text-ink-400">Issued at:</span> <span className="text-ink-900 font-medium">{formatShortDateTime(bill.date)}</span></p>
        {bill.method && <p><span className="text-ink-400">Payment method:</span> <span className="text-ink-900 font-medium">{bill.method}</span></p>}
      </div>

      {bill.bill_type === "pharmacy" && pharmacySale && (
        <>
          <p className="text-ink-900 mt-space-4 mb-space-2 text-[12.5px] font-bold">Pharmacy Bill Breakdown</p>
          <div className="space-y-space-1">
            {pharmacySale.items.map((item) => (
              <div key={item.id} className="flex items-center justify-between text-[12px]">
                <span className="text-ink-700">{item.medicine_name} × {item.quantity}</span>
                <span className="text-ink-900 font-medium">{formatINR(item.line_total)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="border-line bg-paper mt-space-4 rounded-md border p-3">
        <div className="flex justify-between text-[12.5px]"><span className="text-ink-600">Bill Amount</span><span className="text-ink-900 font-semibold">{formatINR(bill.amount)}</span></div>
        <div className="flex justify-between text-[12.5px]"><span className="text-ink-600">Amount Paid</span><span className="text-ink-900 font-semibold">{formatINR(bill.amount_paid)}</span></div>
        {bill.refund_amount > 0 && (
          <div className="flex justify-between text-[12.5px]"><span className="text-ink-600">Refunded</span><span className="text-ink-900 font-semibold">{formatINR(bill.refund_amount)}</span></div>
        )}
        <div className={`mt-space-2 border-t pt-space-2 flex justify-between text-[13px] font-bold ${isSettled ? "border-line" : "border-clay-200"}`}>
          <span className={isSettled ? "text-ink-700" : "text-clay-700"}>Balance Due</span>
          <span className={isSettled ? "text-ink-700" : "text-clay-700"}>{formatINR(Math.max(balanceDue, 0))}</span>
        </div>
      </div>

      {isAppointmentBill && (
        <div className="border-line mt-space-4 rounded-md border p-3">
          <p className="text-ink-900 mb-space-2 text-[12.5px] font-bold">Refund</p>
          {!latestRefund ? (
            <p className="text-hint text-[12px]">No refund request exists for this bill.</p>
          ) : (
            <div className="space-y-space-1 text-[12.5px]">
              <div className="flex justify-between"><span className="text-ink-600">Status</span><Badge tone={latestRefund.status === "completed" ? "success" : latestRefund.status === "rejected" || latestRefund.status === "failed" ? "neutral" : "clay"}>{REFUND_STATUS_LABELS[latestRefund.status] ?? latestRefund.status}</Badge></div>
              <div className="flex justify-between"><span className="text-ink-600">Refund Amount</span><span className="text-ink-900 font-semibold">{formatINR(latestRefund.refund_amount)}</span></div>
              {canWrite && latestRefund.status === "pending_approval" && (
                <Button
                  size="md" variant="secondary" className="mt-space-2 w-full"
                  disabled={approvingId === latestRefund.id}
                  onClick={() => approveRefund(latestRefund.id)}
                >
                  {approvingId === latestRefund.id ? "Processing…" : "Process Refund"}
                </Button>
              )}
            </div>
          )}
        </div>
      )}

      {canWrite && !isSettled && (
        <div className="mt-space-4 space-y-space-2">
          <div className="gap-space-2 flex">
            <select value={method} onChange={(e) => setMethod(e.target.value)} className="border-line bg-card px-space-2 text-ink-900 h-9 rounded-md border text-[12.5px]">
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="upi">UPI</option>
            </select>
            <Input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} className="h-9 flex-1" />
          </div>
          <Button
            disabled={collectCash.isPending || collectingPharmacy}
            onClick={handleCollect}
            className="w-full"
          >
            {collectCash.isPending || collectingPharmacy ? "Collecting…" : `Collect ${formatINR(Number(amount) || balanceDue)}`}
          </Button>
        </div>
      )}
    </Card>
  );
}
