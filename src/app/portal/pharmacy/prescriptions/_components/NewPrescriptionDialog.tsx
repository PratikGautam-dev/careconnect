"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import type { Medicine } from "@/hooks/usePharmacyMedicines";
import type { NewPrescriptionItem, NewPrescriptionPayload } from "@/hooks/usePharmacyPrescriptions";
import { formatDate } from "@/lib/formatDate";

type Line = { medicine_id: string; dosage: string; frequency: string; duration: string; dosage_instructions: string };

function emptyLine(): Line {
  return { medicine_id: "", dosage: "", frequency: "", duration: "", dosage_instructions: "" };
}

/** Optional prefill context -- set when this dialog is opened from a
 * specific appointment (the appointment detail page's embedded
 * Prescriptions panel) or patient page so the created prescription links
 * back to that exact visit/patient/doctor instead of being a free-text
 * walk-in. When `patientName` is given, the field becomes read-only (the
 * patient is already known, not something this dialog should let someone
 * overwrite). `appointmentReferenceId`/`prescribedByName` are purely
 * display text for the form's info header -- neither is stored on the
 * prescription row itself (the row only keeps the numeric appointment_id/
 * prescribing_doctor_id FKs). */
export type PrescriptionPrefill = {
  patientId?: number;
  patientName?: string;
  appointmentId?: number;
  appointmentReferenceId?: string;
  prescribingDoctorId?: string;
  prescribedByName?: string;
  wardOrOpd?: string;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  medicines: Medicine[];
  onSubmit: (payload: NewPrescriptionPayload) => Promise<void>;
  submitting: boolean;
  prefill?: PrescriptionPrefill;
};

/** "+ New Prescription" -- the "Prescription" card layout (info header row
 * + a Medicine/Dosage/Frequency/Duration/Instructions table + General
 * Advice + Follow-up Date + Save Draft/Sign & Send to Pharmacy), matching
 * the reference ERP screenshot. Presentational only, all state/submit
 * logic in usePharmacyPrescriptions.ts; quantity_prescribed (needed for
 * stock deduction) is NOT collected here -- the backend derives it from
 * Frequency+Duration (see pharmacy_prescriptions.py's _derive_quantity()),
 * since this form only asks for the clinical fields a doctor actually
 * writes. "Save Draft" creates with status="draft"; "Sign & Send to
 * Pharmacy" creates with status="pending" directly (skipping the draft
 * stage in one call rather than create-then-sign in two). */
export function NewPrescriptionDialog({ open, onOpenChange, medicines, onSubmit, submitting, prefill }: Props) {
  const [patientName, setPatientName] = useState(prefill?.patientName || "");
  const [wardOrOpd, setWardOrOpd] = useState(prefill?.wardOrOpd || "");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [generalAdvice, setGeneralAdvice] = useState("");
  const [followUpDate, setFollowUpDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [signingSubmit, setSigningSubmit] = useState(false);

  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setPatientName(prefill?.patientName || "");
      setWardOrOpd(prefill?.wardOrOpd || "");
      setLines([emptyLine()]);
      setGeneralAdvice("");
      setFollowUpDate("");
      setError(null);
    }
  }

  function updateLine(index: number, patch: Partial<Line>) {
    setLines((ls) => ls.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  async function handleSubmit(status: "draft" | "pending") {
    if (!patientName.trim()) return setError("Patient name is required.");
    const items: NewPrescriptionItem[] = [];
    for (const line of lines) {
      if (!line.medicine_id) continue;
      items.push({
        medicine_id: Number(line.medicine_id),
        dosage: line.dosage.trim() || undefined,
        frequency: line.frequency.trim() || undefined,
        duration: line.duration.trim() || undefined,
        dosage_instructions: line.dosage_instructions.trim() || undefined,
      });
    }
    if (items.length === 0) return setError("Add at least one medicine.");
    setError(null);
    setSigningSubmit(status === "pending");
    try {
      await onSubmit({
        patient_name: patientName.trim(),
        items,
        ward_or_opd: wardOrOpd.trim() || undefined,
        general_advice: generalAdvice.trim() || undefined,
        follow_up_date: followUpDate || undefined,
        status,
        patient_id: prefill?.patientId,
        appointment_id: prefill?.appointmentId,
        prescribing_doctor_id: prefill?.prescribingDoctorId,
      });
      onOpenChange(false);
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogTitle>New Prescription</DialogTitle>

        <div className="gap-space-3 mt-space-4 grid grid-cols-2">
          <Field label="Patient Name" required>
            <Input
              value={patientName}
              onChange={(e) => setPatientName(e.target.value)}
              disabled={!!prefill?.patientName}
            />
          </Field>
          <Field label="Ward / OPD" hint="Optional">
            <Input value={wardOrOpd} onChange={(e) => setWardOrOpd(e.target.value)} />
          </Field>
        </div>

        <div className="border-line bg-paper mt-space-4 rounded-md border p-3">
          <p className="text-ink-900 mb-space-2 text-[13.5px] font-bold">Prescription</p>
          <div className="gap-space-2 text-[11.5px] grid grid-cols-2 sm:grid-cols-3">
            <div>
              <p className="text-ink-400">Prescription ID</p>
              <p className="text-ink-700 font-mono">Assigned on save</p>
            </div>
            <div>
              <p className="text-ink-400">Prescription Status</p>
              <Badge tone="neutral">Draft</Badge>
            </div>
            <div>
              <p className="text-ink-400">Appointment ID</p>
              <p className="text-ink-700 font-mono">{prefill?.appointmentReferenceId || (prefill?.appointmentId ? `#${prefill.appointmentId}` : "—")}</p>
            </div>
            <div>
              <p className="text-ink-400">Prescribed by</p>
              <p className="text-ink-700">{prefill?.prescribedByName || "—"}</p>
            </div>
            <div>
              <p className="text-ink-400">Created on</p>
              <p className="text-ink-700">{formatDate(new Date().toISOString())}</p>
            </div>
            <div>
              <p className="text-ink-400">Destination</p>
              <Badge tone="brand">Hospital Pharmacy</Badge>
            </div>
          </div>

          <div className="mt-space-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-[12.5px]">
              <thead>
                <tr className="text-ink-400 text-left text-[11px] font-semibold uppercase">
                  <th className="pb-space-1">Medicine</th>
                  <th className="pb-space-1">Dosage</th>
                  <th className="pb-space-1">Frequency</th>
                  <th className="pb-space-1">Duration</th>
                  <th className="pb-space-1">Instructions</th>
                  <th className="pb-space-1" />
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i}>
                    <td className="py-space-1 pr-space-2">
                      <select
                        value={line.medicine_id}
                        onChange={(e) => updateLine(i, { medicine_id: e.target.value })}
                        className="border-line bg-card px-space-2 text-ink-900 h-9 w-full rounded-md border text-[12.5px]"
                      >
                        <option value="">Medicine…</option>
                        {medicines.map((m) => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-space-1 pr-space-2">
                      <Input placeholder="500 mg" value={line.dosage} onChange={(e) => updateLine(i, { dosage: e.target.value })} className="h-9" />
                    </td>
                    <td className="py-space-1 pr-space-2">
                      <Input placeholder="1-0-1" value={line.frequency} onChange={(e) => updateLine(i, { frequency: e.target.value })} className="h-9" />
                    </td>
                    <td className="py-space-1 pr-space-2">
                      <Input placeholder="5 days" value={line.duration} onChange={(e) => updateLine(i, { duration: e.target.value })} className="h-9" />
                    </td>
                    <td className="py-space-1 pr-space-2">
                      <Input placeholder="After food" value={line.dosage_instructions} onChange={(e) => updateLine(i, { dosage_instructions: e.target.value })} className="h-9" />
                    </td>
                    <td className="py-space-1 w-8 text-right">
                      {lines.length > 1 && (
                        <button type="button" onClick={() => setLines((ls) => ls.filter((_, idx) => idx !== i))} className="text-error">
                          <Trash2 size={15} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button type="button" variant="secondary" size="md" onClick={() => setLines((ls) => [...ls, emptyLine()])} className="mt-space-2">
            <Plus size={14} /> Add another medicine
          </Button>

          <div className="gap-space-3 mt-space-4 grid grid-cols-1 sm:grid-cols-2">
            <Field label="General Advice" hint="Optional">
              <Textarea
                value={generalAdvice}
                onChange={(e) => setGeneralAdvice(e.target.value)}
                placeholder="Rest well, maintain adequate hydration, and take a light diet."
                rows={3}
              />
            </Field>
            <Field label="Follow-up Date" hint="Optional">
              <Input type="date" value={followUpDate} onChange={(e) => setFollowUpDate(e.target.value)} />
            </Field>
          </div>
        </div>

        {error && <p className="mt-space-3 text-error text-[12.5px] font-medium">{error}</p>}

        <div className="gap-space-2 mt-space-4 flex flex-wrap">
          <Button type="button" variant="secondary" disabled={submitting} onClick={() => handleSubmit("draft")}>
            {submitting && !signingSubmit ? "Saving…" : "Save Draft"}
          </Button>
          <Button type="button" variant="secondary" disabled title="Available once the prescription is saved">
            Print Prescription
          </Button>
          <Button type="button" className="ml-auto" disabled={submitting} onClick={() => handleSubmit("pending")}>
            {submitting && signingSubmit ? "Sending…" : "Sign & Send to Pharmacy"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
