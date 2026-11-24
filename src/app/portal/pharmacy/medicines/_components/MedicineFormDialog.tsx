"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { emptyMedicineForm, type Medicine, type MedicineForm } from "@/hooks/usePharmacyMedicines";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  medicine?: Medicine | null;
  onSubmit: (form: MedicineForm) => Promise<void>;
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
export function MedicineFormDialog({ open, onOpenChange, medicine, onSubmit, submitting }: Props) {
  const [form, setForm] = useState<MedicineForm>(emptyMedicineForm());
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
      setError(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Medicine name is required.");
      return;
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

          {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Saving…" : medicine ? "Save Changes" : "Add Medicine"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
