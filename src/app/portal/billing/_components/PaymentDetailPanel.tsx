"use client";

import type { LucideIcon } from "lucide-react";
import {
  Calendar,
  CalendarClock,
  CreditCard,
  Hash,
  Phone,
  Receipt,
  Stethoscope,
  User,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { formatDateTime } from "@/lib/formatDate";
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
            ₹{payment.amount.toLocaleString("en-IN")} · Attempt #{payment.attempt_no}
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
    </Card>
  );
}
