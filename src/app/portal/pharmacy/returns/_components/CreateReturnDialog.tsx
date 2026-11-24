"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { Medicine } from "@/hooks/usePharmacyMedicines";
import { fetchMedicine, type MedicineBatch } from "@/hooks/usePharmacyMedicines";
import type { Supplier } from "@/hooks/usePharmacySuppliers";
import type { NewPurchaseReturnPayload, NewSalesReturnPayload, NewStockAdjustmentPayload } from "@/hooks/usePharmacyReturns";

export type ReturnTab = "sales_return" | "purchase_return" | "stock_adjustment";

const SALES_RETURN_REASONS = ["Customer Request", "Expired Stock", "Damaged in Transit", "Wrong Dispensing", "Other"];
const ADJUSTMENT_TYPES = [
  { value: "damage", label: "Damage" },
  { value: "count_correction", label: "Stock Count Correction" },
  { value: "expiry", label: "Expiry Write-off" },
  { value: "other", label: "Other" },
];

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tab: ReturnTab;
  medicines: Medicine[];
  suppliers: Supplier[];
  submitting: boolean;
  onSubmitSalesReturn: (payload: NewSalesReturnPayload) => Promise<void>;
  onSubmitPurchaseReturn: (payload: NewPurchaseReturnPayload) => Promise<void>;
  onSubmitStockAdjustment: (payload: NewStockAdjustmentPayload) => Promise<void>;
};

const TAB_TITLES: Record<ReturnTab, string> = {
  sales_return: "Create Sales Return",
  purchase_return: "Create Purchase Return",
  stock_adjustment: "Adjust Stock",
};

/** One dialog whose fields adapt to the active tab (Sales Returns/Purchase
 * Returns/Stock Adjustments), matching the reference's single "+ Create
 * Return" button -- the field set genuinely differs per type (a sales
 * return restocks from a patient, a purchase return destocks to a
 * supplier, an adjustment has neither), so this switches on `tab` rather
 * than being 3 separate dialog components sharing nothing. */
export function CreateReturnDialog({
  open, onOpenChange, tab, medicines, suppliers, submitting,
  onSubmitSalesReturn, onSubmitPurchaseReturn, onSubmitStockAdjustment,
}: Props) {
  const [medicineId, setMedicineId] = useState("");
  const [batches, setBatches] = useState<MedicineBatch[]>([]);
  const [batchId, setBatchId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitAmount, setUnitAmount] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [reason, setReason] = useState("");
  const [adjustmentType, setAdjustmentType] = useState("damage");
  const [adjustmentDirection, setAdjustmentDirection] = useState<"add" | "remove">("remove");
  const [patientName, setPatientName] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setMedicineId("");
      setBatches([]);
      setBatchId("");
      setQuantity("");
      setUnitAmount("");
      setSupplierId("");
      setReason(tab === "sales_return" ? SALES_RETURN_REASONS[0] : "");
      setAdjustmentType("damage");
      setAdjustmentDirection("remove");
      setPatientName("");
      setNotes("");
      setError(null);
    }
  }

  async function handleMedicineChange(id: string) {
    setMedicineId(id);
    setBatchId("");
    setUnitAmount("");
    if (!id) {
      setBatches([]);
      return;
    }
    const full = await fetchMedicine(Number(id));
    setBatches(full?.batches ?? []);
    const medicine = medicines.find((m) => String(m.id) === id);
    if (medicine?.unit_price != null) setUnitAmount(String(medicine.unit_price));
  }

  function handleBatchChange(id: string) {
    setBatchId(id);
    const batch = batches.find((b) => String(b.id) === id);
    if (batch?.cost_price != null) setUnitAmount(String(batch.cost_price));
  }

  async function handleSubmit() {
    if (!medicineId) return setError("Choose a medicine.");
    const qty = Number(quantity);
    if (!qty || qty <= 0) return setError("Enter a valid quantity.");
    setError(null);
    try {
      if (tab === "sales_return") {
        await onSubmitSalesReturn({
          reason, notes: notes.trim() || undefined,
          items: [{
            medicine_id: Number(medicineId), quantity: qty, unit_price: Number(unitAmount) || 0,
            medicine_batch_id: batchId ? Number(batchId) : undefined,
          }],
        });
      } else if (tab === "purchase_return") {
        if (!supplierId) return setError("Choose a supplier.");
        if (!batchId) return setError("Choose a batch.");
        await onSubmitPurchaseReturn({
          supplier_id: Number(supplierId), reason, notes: notes.trim() || undefined,
          items: [{
            medicine_id: Number(medicineId), quantity: qty, unit_cost: Number(unitAmount) || 0,
            medicine_batch_id: Number(batchId),
          }],
        });
      } else {
        const signedQty = adjustmentDirection === "remove" ? -qty : qty;
        if (adjustmentDirection === "remove" && !batchId) return setError("Choose a batch to deduct from.");
        await onSubmitStockAdjustment({
          medicine_id: Number(medicineId), adjustment_type: adjustmentType, quantity_delta: signedQty,
          medicine_batch_id: batchId ? Number(batchId) : undefined, reason: reason.trim() || undefined,
          notes: notes.trim() || undefined,
        });
      }
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogTitle>{TAB_TITLES[tab]}</DialogTitle>
        <div className="mt-space-4 space-y-space-3">
          <Field label="Medicine" required>
            <select
              value={medicineId}
              onChange={(e) => handleMedicineChange(e.target.value)}
              className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
            >
              <option value="">Medicine…</option>
              {medicines.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </Field>

          {(tab === "purchase_return" || adjustmentDirection === "remove" || tab === "sales_return") && (
            <Field label="Batch" hint={tab === "sales_return" ? "Optional -- which batch to restock" : undefined} required={tab === "purchase_return" || (tab === "stock_adjustment" && adjustmentDirection === "remove")}>
              <select
                value={batchId}
                onChange={(e) => handleBatchChange(e.target.value)}
                disabled={!medicineId}
                className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px] disabled:opacity-50"
              >
                <option value="">Batch…</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>{b.batch_number} -- {b.quantity_on_hand} on hand (exp. {b.expiry_date})</option>
                ))}
              </select>
            </Field>
          )}

          <div className="gap-space-3 grid grid-cols-2">
            {tab === "stock_adjustment" ? (
              <Field label="Direction">
                <select
                  value={adjustmentDirection}
                  onChange={(e) => setAdjustmentDirection(e.target.value as "add" | "remove")}
                  className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
                >
                  <option value="remove">Remove stock</option>
                  <option value="add">Add stock</option>
                </select>
              </Field>
            ) : (
              <Field label={tab === "purchase_return" ? "Unit Cost" : "Unit Price"}>
                <Input type="number" min="0" step="0.01" value={unitAmount} onChange={(e) => setUnitAmount(e.target.value)} />
              </Field>
            )}
            <Field label="Quantity" required>
              <Input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </Field>
          </div>

          {tab === "purchase_return" && (
            <Field label="Supplier" required>
              <select
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
              >
                <option value="">Supplier…</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </Field>
          )}

          {tab === "sales_return" && (
            <Field label="Patient" hint="Optional">
              <Input value={patientName} onChange={(e) => setPatientName(e.target.value)} />
            </Field>
          )}

          {tab === "stock_adjustment" && (
            <Field label="Adjustment Type">
              <select
                value={adjustmentType}
                onChange={(e) => setAdjustmentType(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
              >
                {ADJUSTMENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </Field>
          )}

          {tab === "sales_return" ? (
            <Field label="Reason">
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
              >
                {SALES_RETURN_REASONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </Field>
          ) : (
            <Field label="Reason" hint="Optional">
              <Input value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
          )}

          <Field label="Notes" hint="Optional">
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>

          {error && <p className="text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="button" disabled={submitting} onClick={handleSubmit} className="w-full">
            {submitting ? "Saving…" : TAB_TITLES[tab]}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
