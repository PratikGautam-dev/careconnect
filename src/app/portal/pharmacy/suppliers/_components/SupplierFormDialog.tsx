"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  emptySupplierForm, SUPPLIER_CATEGORIES, SUPPLIER_PAYMENT_TERMS, type Supplier, type SupplierForm,
} from "@/hooks/usePharmacySuppliers";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  supplier?: Supplier | null;
  onSubmit: (form: SupplierForm, is_active: boolean) => Promise<void>;
  submitting: boolean;
};

function formFromSupplier(s: Supplier): SupplierForm {
  return {
    name: s.name, contact_person: s.contact_person || "", phone: s.phone || "", email: s.email || "",
    address: s.address || "", category: s.category || "", payment_terms: s.payment_terms || "",
  };
}

export function SupplierFormDialog({ open, onOpenChange, supplier, onSubmit, submitting }: Props) {
  const [form, setForm] = useState<SupplierForm>(emptySupplierForm());
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setForm(supplier ? formFromSupplier(supplier) : emptySupplierForm());
      setIsActive(supplier ? supplier.is_active : true);
      setError(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Supplier name is required.");
      return;
    }
    setError(null);
    try {
      await onSubmit(form, isActive);
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{supplier ? "Edit Supplier" : "Add Supplier"}</DialogTitle>
        <form onSubmit={handleSubmit} className="mt-space-4">
          <Field label="Name" required>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </Field>
          <Field label="Contact Person">
            <Input value={form.contact_person} onChange={(e) => setForm((f) => ({ ...f, contact_person: e.target.value }))} />
          </Field>
          <div className="gap-space-3 grid grid-cols-2">
            <Field label="Phone">
              <Input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
            </Field>
            <Field label="Email">
              <Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </Field>
          </div>
          <Field label="Address">
            <Input value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} />
          </Field>
          <div className="gap-space-3 grid grid-cols-2">
            <Field label="Category" hint="Optional">
              <select
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
              >
                <option value="">Select…</option>
                {SUPPLIER_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Payment Terms" hint="Optional">
              <select
                value={form.payment_terms}
                onChange={(e) => setForm((f) => ({ ...f, payment_terms: e.target.value }))}
                className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
              >
                <option value="">Select…</option>
                {SUPPLIER_PAYMENT_TERMS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
          </div>
          {supplier && (
            <Field label="Status">
              <select
                value={isActive ? "active" : "inactive"}
                onChange={(e) => setIsActive(e.target.value === "active")}
                className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </Field>
          )}

          {error && <p className="mb-space-3 text-error text-[12.5px] font-medium">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Saving…" : supplier ? "Save Changes" : "Add Supplier"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
