"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import type { Doctor } from "@/hooks/useDoctors";
import type { DepartmentDetail, DepartmentFields } from "@/hooks/useDepartments";

type Props = {
  open: boolean;
  department: DepartmentDetail | null;
  doctors: Doctor[];
  saving: boolean;
  onClose: () => void;
  onSubmit: (fields: DepartmentFields) => void;
};

/** Add/Edit Department -- same form for both (department null = create).
 * Plain fixed-overlay modal, same convention as ConfirmDialog.tsx (this
 * codebase's other hand-rolled modal), rather than the base-ui Dialog
 * primitive. */
export function DepartmentFormDialog({ open, department, doctors, saving, onClose, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [floorWing, setFloorWing] = useState("");
  const [consultationHours, setConsultationHours] = useState("");
  const [description, setDescription] = useState("");
  const [headDoctorId, setHeadDoctorId] = useState("");

  useEffect(() => {
    if (!open) return;
    setName(department?.name || "");
    setFloorWing(department?.floor_wing || "");
    setConsultationHours(department?.consultation_hours || "");
    setDescription(department?.description || "");
    setHeadDoctorId(department?.head_doctor?.id || "");
  }, [open, department]);

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      floor_wing: floorWing.trim() || null,
      consultation_hours: consultationHours.trim() || null,
      description: description.trim() || null,
      head_doctor_id: headDoctorId || null,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-space-4" onClick={onClose}>
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[480px] rounded-lg bg-card p-space-5 shadow-[var(--shadow-lg)]"
      >
        <h2 className="mb-space-4 text-[16px] font-bold text-ink-900">
          {department ? "Edit Department" : "Add Department"}
        </h2>

        <Field label="Department Name" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="Floor / Wing">
          <Input value={floorWing} onChange={(e) => setFloorWing(e.target.value)} placeholder="e.g. 1st Floor, Main Wing" />
        </Field>
        <Field label="Consultation Hours">
          <Input
            value={consultationHours}
            onChange={(e) => setConsultationHours(e.target.value)}
            placeholder="e.g. 9:00 AM - 5:00 PM"
          />
        </Field>
        <Field label="Head of Department">
          <select
            value={headDoctorId}
            onChange={(e) => setHeadDoctorId(e.target.value)}
            className="h-10 w-full rounded-md border border-line bg-card px-space-3 text-[13.5px] text-ink-900"
          >
            <option value="">None</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>{d.name} — {d.department_name}</option>
            ))}
          </select>
        </Field>
        <Field label="Description" className="mb-0">
          <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>

        <div className="mt-space-5 flex justify-end gap-space-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button type="submit" disabled={saving || !name.trim()}>
            {saving ? "Saving…" : department ? "Save Changes" : "Add Department"}
          </Button>
        </div>
      </form>
    </div>
  );
}
