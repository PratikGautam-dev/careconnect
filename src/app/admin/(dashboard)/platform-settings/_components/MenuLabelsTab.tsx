"use client";

import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";

const FEATURE_DISPLAY_NAMES: Record<string, string> = {
  book_doctor_appointment: "Book Doctor Appointment",
  tests_diagnostics: "Tests & Diagnostics",
  procedure: "Daycare / Procedure",
  reschedule: "Reschedule Appointment",
  cancel: "Cancel Appointment",
  view_appointments: "My Appointments",
  reports_prescriptions: "Reports & Prescriptions",
  manage_patients: "Manage Patients",
  consent_privacy: "Consent & Privacy",
  manage_language: "Manage Language",
  hospital_info: "Hospital Information",
  reception_handoff: "Talk to Reception",
  faq: "FAQ / Information",
};

type Props = {
  defaultLabels: Record<string, string>;
  featureLabels: Record<string, string>;
  setFeatureLabel: (key: string, label: string) => void;
};

export function MenuLabelsTab({ defaultLabels, featureLabels, setFeatureLabel }: Props) {
  return (
    <Card className="p-space-5">
      <h2 className="mb-space-1 text-ink-900 text-[15px] font-bold">Menu labels</h2>
      <p className="mb-space-3 text-ink-400 text-[12.5px]">
        Rename how a feature appears in every hospital&apos;s WhatsApp menu. Leave a field blank to
        use the default. Applies platform-wide — a hospital&apos;s own Settings page can no longer
        override this.
      </p>
      {Object.keys(defaultLabels).map((key) => (
        <Field key={key} label={FEATURE_DISPLAY_NAMES[key] || key} htmlFor={`label_${key}`}>
          <Input
            id={`label_${key}`}
            placeholder={defaultLabels[key] || ""}
            value={featureLabels[key] || ""}
            onChange={(e) => setFeatureLabel(key, e.target.value)}
          />
        </Field>
      ))}
    </Card>
  );
}
