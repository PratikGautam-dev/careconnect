"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Banknote } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { cn } from "@/lib/cn";
import { formatINR } from "@/lib/formatCurrency";
import type { Appointment } from "@/hooks/useAppointments";
import { RecordPaymentDialog } from "./RecordPaymentDialog";

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  paid: "Paid",
  pending: "Not paid",
  failed: "Failed",
  pay_at_hospital: "Not paid",
};
export const PAYMENT_STATUS_STYLES: Record<string, string> = {
  paid: "bg-success-tint text-success",
  pending: "bg-clay-100 text-clay-700",
  failed: "bg-error-tint text-error",
  pay_at_hospital: "bg-clay-100 text-clay-700",
};

function methodLabel(a: Appointment): string {
  if (a.payment_method === "cash") return "Cash";
  if (a.payment_method === "online")
    return a.payment_mode ? a.payment_mode.toUpperCase() : "Online";
  return "";
}

/** The appointment tables' Payment column: Paid/Not paid badge (+ cash/online
 * mode and amount), and a "Mark paid" button on unpaid, still-active rows that
 * opens the cash-payment dialog. "Not configured" when the booking never had a
 * payment step (no fee applied). */
export function PaymentCell({ appointment: a }: { appointment: Appointment }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  if (!a.payment_status) {
    return <span className="text-ink-400 text-[12.5px]">Not configured</span>;
  }

  const paid = a.payment_status === "paid";
  const canMarkPaid = !paid && a.status !== "cancelled" && a.status !== "rescheduled";
  const method = paid ? methodLabel(a) : "";

  return (
    <div className="gap-space-1 flex flex-col items-start">
      <span
        className={cn(
          "px-space-2 rounded-full py-0.5 text-[11px] font-semibold whitespace-nowrap",
          PAYMENT_STATUS_STYLES[a.payment_status],
        )}
      >
        {PAYMENT_STATUS_LABELS[a.payment_status]}
        {method && ` · ${method}`}
      </span>
      {a.payment_amount != null && (
        <span className="text-ink-600 text-[11.5px] tabular-nums">
          {formatINR(a.payment_amount)}
        </span>
      )}
      {canMarkPaid && (
        <PermissionGate page="appointments" action="write">
          <Button
            variant="primary"
            onClick={() => setOpen(true)}
            className="px-space-3 h-8 items-center text-[12.5px]"
          >
            <Banknote size={13} /> Mark paid
          </Button>
          <RecordPaymentDialog
            appointment={open ? a : null}
            onOpenChange={setOpen}
            onCollected={() => {
              queryClient.invalidateQueries({ queryKey: ["portal-bookings"] });
              queryClient.invalidateQueries({ queryKey: ["portal-bookings-summary"] });
            }}
          />
        </PermissionGate>
      )}
    </div>
  );
}
