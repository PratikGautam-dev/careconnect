"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { Medicine } from "@/hooks/usePharmacyMedicines";
import type { NewOtcSalePayload } from "@/hooks/usePharmacyBilling";

type Line = { medicine_id: string; quantity: string };
function emptyLine(): Line {
  return { medicine_id: "", quantity: "" };
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  medicines: Medicine[];
  submitting: boolean;
  onSubmit: (payload: NewOtcSalePayload) => Promise<void>;
};

/** "+ New Bill" -- creates an OTC (walk-in) or IPD-context sale directly
 * from the medicine catalog, no prescription behind it. Presentational
 * only; submit logic lives in usePharmacyBilling's createOtcSale. */
export function NewOtcSaleDialog({ open, onOpenChange, medicines, submitting, onSubmit }: Props) {
  const [saleType, setSaleType] = useState<"otc" | "ipd">("otc");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [error, setError] = useState<string | null>(null);

  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setSaleType("otc");
      setLines([emptyLine()]);
      setError(null);
    }
  }

  function updateLine(index: number, patch: Partial<Line>) {
    setLines((ls) => ls.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  async function handleSubmit() {
    const items = lines
      .filter((l) => l.medicine_id && l.quantity)
      .map((l) => ({ medicine_id: Number(l.medicine_id), quantity: Number(l.quantity) }));
    if (items.length === 0) return setError("Add at least one medicine.");
    setError(null);
    try {
      await onSubmit({ sale_type: saleType, items });
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogTitle>New Bill</DialogTitle>
        <div className="mt-space-4 space-y-space-3">
          <Field label="Bill Type">
            <div className="gap-space-1 border-line bg-paper flex rounded-md border p-0.5">
              {(["otc", "ipd"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSaleType(t)}
                  className={`flex-1 rounded px-3 py-1.5 text-[12.5px] font-semibold transition-colors duration-150 ${
                    saleType === t ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]" : "text-ink-400 hover:text-ink-700"
                  }`}
                >
                  {t === "otc" ? "OTC Sale" : "IPD Bill"}
                </button>
              ))}
            </div>
          </Field>

          <p className="text-label mb-space-2">Medicines</p>
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
                  type="number" min="1" placeholder="Qty" value={line.quantity}
                  onChange={(e) => updateLine(i, { quantity: e.target.value })}
                  className="w-24"
                />
                {lines.length > 1 && (
                  <button type="button" onClick={() => setLines((ls) => ls.filter((_, idx) => idx !== i))} className="text-error shrink-0">
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            ))}
          </div>
          <Button type="button" variant="secondary" size="md" onClick={() => setLines((ls) => [...ls, emptyLine()])}>
            <Plus size={14} /> Add medicine
          </Button>

          {error && <p className="text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="button" disabled={submitting} onClick={handleSubmit} className="w-full">
            {submitting ? "Creating…" : "Create Bill"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
