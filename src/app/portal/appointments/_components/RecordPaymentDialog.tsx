"use client";

import { useState } from "react";
import { Banknote } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { useCollectCashPayment } from "@/hooks/useAppointmentDetail";
import { toast } from "@/lib/toast";
import type { Appointment } from "@/hooks/useAppointments";

type Props = {
  appointment: Appointment | null;
  onOpenChange: (open: boolean) => void;
  onCollected: () => void;
};

/** Front-desk "cash actually collected" confirmation -- opened from the
 * appointment detail page, never the appointments table (this only ever
 * makes sense against ONE specific appointment's own resolved fee). Cash
 * only, no method picker -- online payments are already confirmed by
 * Razorpay's own webhook, this dialog exists purely for the gap that leaves
 * open (a patient who chose "Pay at Hospital", or a stalled online attempt
 * staff is overriding). */
export function RecordPaymentDialog({ appointment, onOpenChange, onCollected }: Props) {
  const open = appointment !== null;
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const collect = useCollectCashPayment();

  // Fresh mount every time this opens (parent only renders a truthy
  // `appointment` once selected) would be ideal, but this dialog stays
  // mounted across opens/closes on the same page -- reset fields explicitly
  // whenever a DIFFERENT appointment becomes the target instead.
  const [lastAppointmentId, setLastAppointmentId] = useState<number | null>(null);
  if (appointment && appointment.id !== lastAppointmentId) {
    setLastAppointmentId(appointment.id);
    setAmount(appointment.payment_amount != null ? String(appointment.payment_amount) : "");
    setReference("");
    setError(null);
  }

  async function handleSubmit() {
    if (!appointment) return;
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError("Enter an amount greater than zero.");
      return;
    }
    setError(null);
    try {
      await collect.mutateAsync({
        appointmentId: String(appointment.id),
        amount: parsed,
        reference,
      });
      toast.success("Payment recorded");
      onOpenChange(false);
      onCollected();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't record payment.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>Record cash payment</DialogTitle>
        <p className="text-hint mb-space-4">
          Confirms this hospital actually collected the payment in cash -- marks the appointment as
          paid.
        </p>

        <Field label="Amount collected (₹)" required error={error || undefined}>
          <Input
            type="number"
            min={0}
            step="0.01"
            value={amount}
            invalid={!!error}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
        <Field
          label="Reference (optional)"
          hint="A receipt number, UPI reference, or any note for your own records."
        >
          <Input
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="e.g. Receipt #1042"
          />
        </Field>

        <Button onClick={handleSubmit} disabled={collect.isPending} className="w-full">
          <Banknote size={14} /> {collect.isPending ? "Recording…" : "Record payment"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
