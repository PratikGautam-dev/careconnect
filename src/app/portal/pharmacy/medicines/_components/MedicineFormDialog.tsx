"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { emptyMedicineForm, type Medicine, type MedicineForm } from "@/hooks/usePharmacyMedicines";

type InitialStock = { batch_number: string; expiry_date: string; quantity: string; cost_price: string };

function emptyInitialStock(): InitialStock {
  return { batch_number: "", expiry_date: "", quantity: "", cost_price: "" };
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  medicine?: Medicine | null;
  /** Returns the created/updated medicine so a new medicine's id is known
   * for the optional initial-stock batch below (edit path returns the same
   * shape too, but this dialog only shows/uses the batch fields for a new
   * medicine -- editing goes through Inventory's own "Add Stock" instead). */
  onSubmit: (form: MedicineForm) => Promise<Medicine | void>;
  /** Adds the optional initial batch once the new medicine exists.
   * Omitted entirely hides the "Initial Stock" section (e.g. from a future
   * caller that doesn't have inventory write access wired up). */
  onAddInitialStock?: (medicineId: number, batch: InitialStock) => Promise<void>;
  submitting: boolean;
};

function formFromMedicine(m: Medicine): MedicineForm {
  return {
    name: m.name,
    generic_name: m.generic_name || "",
    category: m.category || "",
    manufacturer: m.manufacturer || "",
    unit: m.unit,
    unit_price: m.unit_price != null ? String(m.unit_price) : "",
    reorder_level: String(m.reorder_level),
  };
}

/** Add/Edit Medicine -- presentational only, the create/update mutations
 * live in usePharmacyMedicines.ts, same template as every other
 * NewXDialog in this app (form state + submit logic in a paired hook). */
export function MedicineFormDialog({ open, onOpenChange, medicine, onSubmit, onAddInitialStock, submitting }: Props) {
  const [form, setForm] = useState<MedicineForm>(emptyMedicineForm());
  const [stock, setStock] = useState<InitialStock>(emptyInitialStock());
  const [error, setError] = useState<string | null>(null);
  // Resets the form the moment `open` flips true -- a render-phase state
  // adjustment (React's own recommended pattern for "reset state when a
  // prop changes"), not an effect, since a synchronous setState inside
  // useEffect here would trigger a flagged extra cascading render.
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setForm(medicine ? formFromMedicine(medicine) : emptyMedicineForm());
      setStock(emptyInitialStock());
      setError(null);
    }
  }

  const showInitialStock = !medicine && !!onAddInitialStock;
  // The whole section is optional -- a medicine can be cataloged with no
  // stock yet -- but once any field is touched, all of batch/expiry/
  // quantity are needed together (a batch with no expiry or quantity isn't
  // a real batch), matching Add Stock's own required-fields rule.
  const stockTouched = stock.batch_number.trim() || stock.expiry_date || stock.quantity || stock.cost_price;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Medicine name is required.");
      return;
    }
    if (showInitialStock && stockTouched) {
      if (!stock.batch_number.trim()) return setError("A batch number is required for the initial stock.");
      if (!stock.expiry_date) return setError("An expiry date is required for the initial stock.");
      if (!stock.quantity || Number(stock.quantity) <= 0) return setError("Initial stock quantity must be greater than zero.");
    }
    setError(null);
    try {
      const result = await onSubmit(form);
      if (showInitialStock && stockTouched && result && onAddInitialStock) {
        await onAddInitialStock(result.id, stock);
      }
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{medicine ? "Edit Medicine" : "Add Medicine"}</DialogTitle>
        <form onSubmit={handleSubmit} className="mt-space-4">
          <Field label="Name" required>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Paracetamol 500mg" />
          </Field>
          <Field label="Generic Name">
            <Input value={form.generic_name} onChange={(e) => setForm((f) => ({ ...f, generic_name: e.target.value }))} />
          </Field>
          <div className="gap-space-3 grid grid-cols-2">
            <Field label="Category">
              <Input value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} placeholder="Tablet, Syrup…" />
            </Field>
            <Field label="Manufacturer">
              <Input value={form.manufacturer} onChange={(e) => setForm((f) => ({ ...f, manufacturer: e.target.value }))} />
            </Field>
          </div>
          <div className="gap-space-3 grid grid-cols-3">
            <Field label="Unit">
              <Input value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} placeholder="strip, bottle…" />
            </Field>
            <Field label="Unit Price (₹)">
              <Input type="number" min="0" step="0.01" value={form.unit_price} onChange={(e) => setForm((f) => ({ ...f, unit_price: e.target.value }))} />
            </Field>
            <Field label="Reorder Level">
              <Input type="number" min="0" value={form.reorder_level} onChange={(e) => setForm((f) => ({ ...f, reorder_level: e.target.value }))} />
            </Field>
          </div>

          {showInitialStock && (
            <div className="mb-space-4 border-line mt-space-2 rounded-md border p-3">
              <p className="text-ink-900 mb-space-2 text-[12.5px] font-bold">Initial Stock (optional)</p>
              <p className="text-hint mb-space-3">
                Give this medicine a first batch now -- this is also where its expiry date comes from (it lives
                on the batch, not the medicine itself, since a medicine can have several batches expiring at
                different times). You can always add more stock later from the Inventory page.
              </p>
              <div className="gap-space-3 grid grid-cols-2">
                <Field label="Batch Number">
                  <Input value={stock.batch_number} onChange={(e) => setStock((s) => ({ ...s, batch_number: e.target.value }))} />
                </Field>
                <Field label="Expiry Date">
                  <Input type="date" value={stock.expiry_date} onChange={(e) => setStock((s) => ({ ...s, expiry_date: e.target.value }))} />
                </Field>
              </div>
              <div className="gap-space-3 grid grid-cols-2">
                <Field label="Quantity">
                  <Input type="number" min="1" value={stock.quantity} onChange={(e) => setStock((s) => ({ ...s, quantity: e.target.value }))} />
                </Field>
                <Field label="Cost Price (₹)">
                  <Input type="number" min="0" step="0.01" value={stock.cost_price} onChange={(e) => setStock((s) => ({ ...s, cost_price: e.target.value }))} />
                </Field>
              </div>
            </div>
          )}

          {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Saving…" : medicine ? "Save Changes" : "Add Medicine"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
