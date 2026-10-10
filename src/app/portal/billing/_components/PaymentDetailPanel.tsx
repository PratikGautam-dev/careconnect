"use client";

import type { LucideIcon } from "lucide-react";
import {
  Calendar,
  CalendarClock,
  CreditCard,
  ExternalLink,
  FileText,
  Hash,
  Phone,
  Receipt,
  Send,
  Stethoscope,
  User,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { usePaymentInvoice } from "@/hooks/usePaymentInvoice";
import { formatDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import type { PaymentRow } from "@/hooks/usePayments";
import {
  PAYMENT_METHOD_LABELS,
  PAYMENT_STATUS_LABELS,
  PAYMENT_STATUS_TONES,
} from "./billing-columns";

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="gap-space-3 flex items-center justify-between text-[13px]">
      <span className="gap-space-2 text-ink-400 flex items-center">
        <Icon size={14} className="shrink-0" /> {label}
      </span>
      <span className="text-ink-900 truncate text-right font-medium">{value}</span>
    </div>
  );
}

type Props = {
  payment: PaymentRow | null;
};

const INVOICE_STATUS_LABELS: Record<string, string> = {
  issued: "Issued",
  paid: "Paid",
  expired: "Expired",
  cancelled: "Cancelled",
};

/** Razorpay's own invoice for an online attempt (no CareConnect-side
 * numbering -- the inv_... id is the invoice identifier). "Send to
 * patient" is WhatsApp-only and only for a paid attempt; every send is
 * audited server-side (portal/routes/payments.py). */
function InvoiceSection({ payment }: { payment: PaymentRow }) {
  const { sendingInvoiceId, viewInvoice, sendInvoice } = usePaymentInvoice();
  const hasInvoice = !!(payment.razorpay_invoice_id || payment.invoice_short_url);
  const canSend = hasInvoice && payment.status === "paid";
  const sending = sendingInvoiceId === payment.id;

  function handleView() {
    if (payment.invoice_short_url) {
      window.open(payment.invoice_short_url, "_blank", "noopener,noreferrer");
    } else {
      void viewInvoice(payment.id);
    }
  }

  return (
    <div className="mt-space-4 border-line pt-space-3 border-t">
      <p className="text-label mb-space-2 text-ink-900 font-bold">Invoice</p>
      {hasInvoice ? (
        <>
          <div className="space-y-space-2">
            <DetailRow
              icon={FileText}
              label="Invoice ID"
              value={payment.razorpay_invoice_id || "—"}
            />
            <DetailRow
              icon={FileText}
              label="Status"
              value={
                payment.invoice_status
                  ? (INVOICE_STATUS_LABELS[payment.invoice_status] ?? payment.invoice_status)
                  : "—"
              }
            />
          </div>
          <div className="mt-space-3 gap-space-2 grid grid-cols-2">
            <Button variant="secondary" onClick={handleView}>
              <ExternalLink size={14} /> View invoice
            </Button>
            {canSend && (
              <Button
                variant="primary"
                disabled={sending}
                onClick={() => void sendInvoice(payment.id)}
              >
                <Send size={14} /> {sending ? "Sending…" : "Send to patient"}
              </Button>
            )}
          </div>
          {canSend && (
            <p className="mt-space-2 text-ink-400 text-[11.5px]">
              Sent on WhatsApp. WhatsApp only delivers if the patient messaged the hospital in the
              last 24 hours.
            </p>
          )}
        </>
      ) : (
        <p className="text-ink-400 text-[12.5px]">No Razorpay invoice for this payment.</p>
      )}
    </div>
  );
}

/** Right-rail "selected transaction" detail card -- same layout convention
 * as StaffDetailPanel.tsx (avatar-less header + a DetailRow stack), every
 * field here is a real payments/appointments column (usePayments.ts). */
export function PaymentDetailPanel({ payment }: Props) {
  if (!payment) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-ink-400 text-center text-[13px]">
          Select a transaction to view its details.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 gap-space-3 flex items-center justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="text-ink-900 truncate text-[15px] font-bold">
            {payment.patient_name || "Unknown patient"}
          </p>
          <p className="text-ink-600 truncate text-[12.5px]">
            {formatINR(payment.amount)} · Attempt #{payment.attempt_no}
          </p>
        </div>
        <Badge tone={PAYMENT_STATUS_TONES[payment.status]}>
          {PAYMENT_STATUS_LABELS[payment.status]}
        </Badge>
      </div>

      <div className="space-y-space-2 border-line pt-space-3 border-t">
        <DetailRow icon={User} label="Patient" value={payment.patient_name || "—"} />
        <DetailRow icon={Phone} label="Phone" value={payment.patient_phone || "—"} />
        <DetailRow icon={Stethoscope} label="Doctor" value={payment.doctor_name || "—"} />
        <DetailRow icon={Hash} label="Reference" value={payment.reference_id || "—"} />
        <DetailRow
          icon={Calendar}
          label="Appointment"
          value={
            payment.appointment_scheduled_at
              ? formatDateTime(payment.appointment_scheduled_at)
              : "—"
          }
        />
      </div>

      <div className="mt-space-3 gap-space-2 grid grid-cols-2">
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <CreditCard size={12} /> Method
          </p>
          <p className="text-ink-900 text-[13px] font-bold">
            {PAYMENT_METHOD_LABELS[payment.method]}
          </p>
        </div>
        <div className="border-line bg-paper p-space-3 rounded-md border">
          <p className="mb-space-1 gap-space-1 text-ink-400 flex items-center text-[11px] font-semibold">
            <CalendarClock size={12} /> Paid at
          </p>
          <p className="text-ink-900 text-[13px] font-bold">
            {payment.paid_at ? formatDateTime(payment.paid_at) : "—"}
          </p>
        </div>
      </div>

      {(payment.base_amount != null || payment.refund_amount != null) && (
        <div className="mt-space-4 border-line pt-space-3 border-t">
          <p className="text-label mb-space-2 text-ink-900 font-bold">Fee Breakdown</p>
          <div className="space-y-space-2">
            {payment.base_amount != null && (
              <DetailRow icon={Receipt} label="Base fee" value={formatINR(payment.base_amount)} />
            )}
            {(payment.gst_amount ?? 0) > 0 && (
              <DetailRow icon={Receipt} label="GST" value={formatINR(payment.gst_amount)} />
            )}
            {(payment.platform_fee_amount ?? 0) > 0 && (
              <DetailRow
                icon={Receipt}
                label="Platform fee"
                value={formatINR(payment.platform_fee_amount)}
              />
            )}
            {payment.refund_amount != null && (
              <DetailRow
                icon={Receipt}
                label="Refunded"
                value={`${formatINR(payment.refund_amount)}${
                  payment.refunded_at ? ` on ${formatDateTime(payment.refunded_at)}` : ""
                }`}
              />
            )}
          </div>
        </div>
      )}

      {payment.method === "pay_at_hospital" ? (
        <div className="mt-space-4 border-line pt-space-3 border-t">
          <p className="text-label mb-space-2 text-ink-900 font-bold">Collection Details</p>
          <div className="space-y-space-2">
            <DetailRow icon={Receipt} label="Reference" value={payment.bank_reference || "—"} />
            <DetailRow icon={Calendar} label="Created" value={formatDateTime(payment.created_at)} />
          </div>
        </div>
      ) : (
        <div className="mt-space-4 border-line pt-space-3 border-t">
          <p className="text-label mb-space-2 text-ink-900 font-bold">Razorpay Details</p>
          <div className="space-y-space-2">
            <DetailRow icon={Receipt} label="Order ID" value={payment.razorpay_order_id || "—"} />
            <DetailRow
              icon={Receipt}
              label="Payment ID"
              value={payment.razorpay_payment_id || "—"}
            />
            <DetailRow icon={Calendar} label="Created" value={formatDateTime(payment.created_at)} />
          </div>
        </div>
      )}

      {payment.method === "online" && <InvoiceSection payment={payment} />}
    </Card>
  );
}
