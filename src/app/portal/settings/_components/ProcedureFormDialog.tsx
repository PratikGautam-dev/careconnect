"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { Department } from "@/hooks/useDepartments";
import {
  PROCEDURE_BOOKING_MODES,
  PROCEDURE_CATEGORIES,
  type Procedure,
  type ProcedureFields,
} from "@/hooks/useProcedures";

type Props = {
  open: boolean;
  procedure: Procedure | null;
  departments: Department[];
  saving: boolean;
  onClose: () => void;
  onSubmit: (fields: ProcedureFields) => void;
};

/** Add/Edit Procedure -- same form for both (procedure null = create), same
 * plain fixed-overlay modal convention as DepartmentFormDialog.tsx. Backs
 * the Procedures settings tab, the first admin UI over the daycare/procedure
 * catalog's already-existing POST/PUT /api/portal/procedures CRUD
 * (portal/routes/procedures.py). */
export function ProcedureFormDialog({
  open,
  procedure,
  departments,
  saving,
  onClose,
  onSubmit,
}: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState<string>(PROCEDURE_CATEGORIES[0].value);
  const [bookingMode, setBookingMode] = useState<"instant" | "approval_required">("instant");
  const [durationMinutes, setDurationMinutes] = useState("30");
  const [departmentId, setDepartmentId] = useState("");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");

  useEffect(() => {
    if (!open) return;
    setName(procedure?.name || "");
    setCategory(procedure?.category || PROCEDURE_CATEGORIES[0].value);
    setBookingMode(procedure?.booking_mode || "instant");
    setDurationMinutes(procedure ? String(procedure.duration_minutes) : "30");
    setDepartmentId(procedure?.department_id || "");
    setPriceMin(procedure?.estimated_price_min != null ? String(procedure.estimated_price_min) : "");
    setPriceMax(procedure?.estimated_price_max != null ? String(procedure.estimated_price_max) : "");
  }, [open, procedure]);

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const duration = Number(durationMinutes);
    if (!duration || duration <= 0) return;
    onSubmit({
      category,
      name: name.trim(),
      booking_mode: bookingMode,
      duration_minutes: duration,
      department_id: departmentId || null,
      estimated_price_min: priceMin === "" ? null : Number(priceMin),
      estimated_price_max: priceMax === "" ? null : Number(priceMax),
    });
  }

  const valid = !!name.trim() && Number(durationMinutes) > 0;

  return (
    <div
      className="p-space-4 fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        className="bg-card p-space-5 w-full max-w-[480px] rounded-lg shadow-[var(--shadow-lg)]"
      >
        <h2 className="mb-space-4 text-ink-900 text-[16px] font-bold">
          {procedure ? "Edit Procedure" : "Add Procedure"}
        </h2>

        <Field label="Procedure Name" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="Category" required>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
          >
            {PROCEDURE_CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Booking Mode" required>
          <select
            value={bookingMode}
            onChange={(e) => setBookingMode(e.target.value as "instant" | "approval_required")}
            className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
          >
            {PROCEDURE_BOOKING_MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Duration (minutes)" required>
          <Input
            type="number"
            min={1}
            value={durationMinutes}
            onChange={(e) => setDurationMinutes(e.target.value)}
          />
        </Field>
        <Field label="Department">
          <select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
          >
            <option value="">None</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </Field>
        <div className="gap-space-3 grid grid-cols-2">
          <Field label="Estimated Price Min (₹)">
            <Input
              type="number"
              min={0}
              placeholder="No price"
              value={priceMin}
              onChange={(e) => setPriceMin(e.target.value)}
            />
          </Field>
          <Field label="Estimated Price Max (₹)" className="mb-0">
            <Input
              type="number"
              min={0}
              placeholder="No price"
              value={priceMax}
              onChange={(e) => setPriceMax(e.target.value)}
            />
          </Field>
        </div>

        <div className="mt-space-5 gap-space-2 flex justify-end">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving || !valid}>
            {saving ? "Saving…" : procedure ? "Save Changes" : "Add Procedure"}
          </Button>
        </div>
      </form>
    </div>
  );
}
