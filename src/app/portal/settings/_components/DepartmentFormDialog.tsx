"use client";

import { useState } from "react";
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
export function DepartmentFormDialog({
  open,
  department,
  doctors,
  saving,
  onClose,
  onSubmit,
}: Props) {
  const [name, setName] = useState("");
  const [floorWing, setFloorWing] = useState("");
  const [consultationHours, setConsultationHours] = useState("");
  const [description, setDescription] = useState("");
  const [headDoctorId, setHeadDoctorId] = useState("");

  // Resets the form from `department` whenever the dialog opens, or a
  // different department is targeted while it's already open -- adjusted
  // directly in the render body (comparing against the previous `open`/
  // `department`) rather than in an effect, per React's own "Adjusting
  // some state when a prop changes" guide. Mirrors the original effect's
  // `[open, department]` dependency array firing on either change, only
  // acting `if (open)`.
  const [prevOpen, setPrevOpen] = useState(open);
  const [prevDepartment, setPrevDepartment] = useState(department);
  if (open !== prevOpen || department !== prevDepartment) {
    setPrevOpen(open);
    setPrevDepartment(department);
    if (open) {
      setName(department?.name || "");
      setFloorWing(department?.floor_wing || "");
      setConsultationHours(department?.consultation_hours || "");
      setDescription(department?.description || "");
      setHeadDoctorId(department?.head_doctor?.id || "");
    }
  }

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
          {department ? "Edit Department" : "Add Department"}
        </h2>

        <Field label="Department Name" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="Floor / Wing">
          <Input
            value={floorWing}
            onChange={(e) => setFloorWing(e.target.value)}
            placeholder="e.g. 1st Floor, Main Wing"
          />
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
            className="border-line bg-card px-space-3 text-ink-900 h-10 w-full rounded-md border text-[13.5px]"
          >
            <option value="">None</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} — {d.department_name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Description" className="mb-0">
          <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>

        <div className="mt-space-5 gap-space-2 flex justify-end">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving || !name.trim()}>
            {saving ? "Saving…" : department ? "Save Changes" : "Add Department"}
          </Button>
        </div>
      </form>
    </div>
  );
}
