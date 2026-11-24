"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { Medicine } from "@/hooks/usePharmacyMedicines";
import type { NewPurchaseOrderItem } from "@/hooks/usePharmacyPurchaseOrders";
import type { Supplier } from "@/hooks/usePharmacySuppliers";

type Line = { medicine_id: string; quantity_ordered: string; unit_cost: string };

function emptyLine(): Line {
  return { medicine_id: "", quantity_ordered: "", unit_cost: "" };
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  medicines: Medicine[];
  suppliers: Supplier[];
  onSubmit: (payload: { supplier_id: number; order_date: string; items: NewPurchaseOrderItem[]; notes?: string }) => Promise<void>;
  submitting: boolean;
};

export function NewPurchaseOrderDialog({ open, onOpenChange, medicines, suppliers, onSubmit, submitting }: Props) {
  const [supplierId, setSupplierId] = useState("");
  const [orderDate, setOrderDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [error, setError] = useState<string | null>(null);

  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setSupplierId("");
      setOrderDate(new Date().toISOString().slice(0, 10));
      setNotes("");
      setLines([emptyLine()]);
      setError(null);
    }
  }

  function updateLine(index: number, patch: Partial<Line>) {
    setLines((ls) => ls.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!supplierId) return setError("Choose a supplier.");
    const items: NewPurchaseOrderItem[] = [];
    for (const line of lines) {
      if (!line.medicine_id || !line.quantity_ordered) continue;
      items.push({
        medicine_id: Number(line.medicine_id),
        quantity_ordered: Number(line.quantity_ordered),
        unit_cost: line.unit_cost ? Number(line.unit_cost) : null,
      });
    }
    if (items.length === 0) return setError("Add at least one item.");
    setError(null);
    try {
      await onSubmit({ supplier_id: Number(supplierId), order_date: orderDate, items, notes: notes.trim() || undefined });
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogTitle>Raise Purchase Order</DialogTitle>
        <form onSubmit={handleSubmit} className="mt-space-4">
          <div className="gap-space-3 grid grid-cols-2">
            <Field label="Supplier" required>
              <select
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
              >
                <option value="">Choose…</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Order Date" required>
              <Input type="date" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} />
            </Field>
          </div>

          <p className="text-label mb-space-2">Items</p>
          <div className="space-y-space-2 mb-space-3">
            {lines.map((line, i) => (
              <div key={i} className="gap-space-2 flex items-end">
                <select
                  value={line.medicine_id}
                  onChange={(e) => updateLine(i, { medicine_id: e.target.value })}
                  className="border-line bg-card px-space-3 text-ink-900 h-10 flex-1 rounded-md border text-[13.5px]"
                >
                  <option value="">Medicine…</option>
                  {medicines.map((m) => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
                <Input
                  type="number" min="1" placeholder="Qty" value={line.quantity_ordered}
                  onChange={(e) => updateLine(i, { quantity_ordered: e.target.value })}
                  className="w-20"
                />
                <Input
                  type="number" min="0" step="0.01" placeholder="Unit cost" value={line.unit_cost}
                  onChange={(e) => updateLine(i, { unit_cost: e.target.value })}
                  className="w-28"
                />
                {lines.length > 1 && (
                  <button type="button" onClick={() => setLines((ls) => ls.filter((_, idx) => idx !== i))} className="text-error shrink-0">
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            ))}
          </div>
          <Button type="button" variant="secondary" size="md" onClick={() => setLines((ls) => [...ls, emptyLine()])} className="mb-space-4">
            <Plus size={14} /> Add item
          </Button>

          <Field label="Notes" hint="Optional">
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>

          {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Creating…" : "Create Purchase Order"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
