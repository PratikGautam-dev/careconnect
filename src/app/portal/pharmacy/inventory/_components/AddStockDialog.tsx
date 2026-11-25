"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { Medicine } from "@/hooks/usePharmacyMedicines";
import { emptyAddStockForm, type AddStockForm } from "@/hooks/usePharmacyInventory";
import type { Supplier } from "@/hooks/usePharmacySuppliers";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  medicines: Medicine[];
  suppliers: Supplier[];
  onSubmit: (form: AddStockForm) => Promise<void>;
  submitting: boolean;
};

/** "Add Stock" quick action -- a standalone batch add with no purchase
 * order behind it (POST .../inventory/add-stock, purchase_order_id stays
 * null server-side). Receiving a PO's delivery is a separate flow on the
 * Purchase Order detail page. */
export function AddStockDialog({ open, onOpenChange, medicines, suppliers, onSubmit, submitting }: Props) {
  const [form, setForm] = useState<AddStockForm>(emptyAddStockForm());
  const [error, setError] = useState<string | null>(null);
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setForm(emptyAddStockForm());
      setError(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.medicine_id) return setError("Choose a medicine.");
    if (!form.batch_number.trim()) return setError("A batch number is required.");
    if (!form.expiry_date) return setError("An expiry date is required.");
    if (!form.quantity || !Number.isInteger(Number(form.quantity)) || Number(form.quantity) <= 0) {
      return setError("Quantity must be a whole number greater than zero.");
    }
    if (form.cost_price && (!Number.isFinite(Number(form.cost_price)) || Number(form.cost_price) < 0)) {
      return setError("Cost price can't be negative.");
    }
    setError(null);
    try {
      await onSubmit(form);
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Add Stock</DialogTitle>
        <form onSubmit={handleSubmit} className="mt-space-4">
          <Field label="Medicine" required>
            <select
              value={form.medicine_id}
              onChange={(e) => setForm((f) => ({ ...f, medicine_id: e.target.value }))}
              className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
            >
              <option value="">Choose…</option>
              {medicines.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </Field>
          <div className="gap-space-3 grid grid-cols-2">
            <Field label="Batch Number" required>
              <Input value={form.batch_number} onChange={(e) => setForm((f) => ({ ...f, batch_number: e.target.value }))} />
            </Field>
            <Field label="Expiry Date" required>
              <Input type="date" value={form.expiry_date} onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))} />
            </Field>
          </div>
          <div className="gap-space-3 grid grid-cols-2">
            <Field label="Quantity" required>
              <Input type="number" min="1" step="1" value={form.quantity} onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))} />
            </Field>
            <Field label="Cost Price (₹)">
              <Input type="number" min="0" step="0.01" value={form.cost_price} onChange={(e) => setForm((f) => ({ ...f, cost_price: e.target.value }))} />
            </Field>
          </div>
          <Field label="Supplier" hint="Optional">
            <select
              value={form.supplier_id}
              onChange={(e) => setForm((f) => ({ ...f, supplier_id: e.target.value }))}
              className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
            >
              <option value="">None</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </Field>

          {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Adding…" : "Add Stock"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
