"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { formatINR } from "@/lib/formatCurrency";
import type { PharmacySale } from "@/hooks/usePharmacyBilling";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sale: PharmacySale | null;
  onSubmit: (paymentMethod: string, paymentAmount: number) => Promise<void>;
  submitting: boolean;
};

const METHODS = ["cash", "card", "upi", "bank_transfer"];

export function CollectPaymentDialog({ open, onOpenChange, sale, onSubmit, submitting }: Props) {
  const [method, setMethod] = useState("cash");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open && sale) {
      setMethod("cash");
      setAmount(String(sale.total_amount));
      setError(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!amount || !Number.isFinite(Number(amount)) || Number(amount) <= 0) return setError("Enter a valid amount.");
    setError(null);
    try {
      await onSubmit(method, Number(amount));
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  if (!sale) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Collect Payment -- {sale.sale_number}</DialogTitle>
        <p className="text-hint mb-space-4 text-[13px]">Total due: {formatINR(sale.total_amount)}</p>
        <form onSubmit={handleSubmit}>
          <Field label="Payment Method" required>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
            >
              {METHODS.map((m) => (
                <option key={m} value={m}>{m.replace("_", " ")}</option>
              ))}
            </select>
          </Field>
          <Field label="Amount (₹)" required>
            <Input type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>

          {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Collecting…" : "Collect Payment"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
