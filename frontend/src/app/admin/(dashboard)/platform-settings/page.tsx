"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CheckboxRow } from "@/components/ui/Checkbox";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { usePlatformSettings } from "@/hooks/usePlatformSettings";

const FEATURE_DISPLAY_NAMES: Record<string, string> = {
  booking: "Book Appointment",
  reschedule: "Reschedule Appointment",
  cancel: "Cancel Appointment",
  view_appointments: "My Appointments",
  reports_prescriptions: "Reports & Prescriptions",
  manage_patients: "Manage Patients",
  consent_privacy: "Consent & Privacy",
  hospital_info: "Hospital Information",
  reception_handoff: "Talk to Reception",
  faq: "FAQ / Information",
};

function PlatformSettingsForm() {
  const {
    settings,
    maxActiveLinks,
    setMaxActiveLinks,
    featureLabels,
    setFeatureLabel,
    dpdpRequired,
    setDpdpRequired,
    error,
    saved,
    saving,
    handleSubmit,
  } = usePlatformSettings();

  return (
    <div>
      <div className="mb-space-5">
        <p className="text-eyebrow mb-space-1">Platform admin</p>
        <h1 className="text-display">Platform settings</h1>
        <p className="text-[13px] text-ink-600">
          Global values that apply identically across every hospital — no per-tenant override.
        </p>
      </div>

      {!settings ? (
        <Card className="p-space-5">
          <p className="py-space-4 text-center text-[13px] text-ink-400">Loading…</p>
        </Card>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-space-5">
          <Card className="p-space-5">
            <Field
              label="Max active patient links"
              htmlFor="max_active_patient_links"
              hint="How many patients a single WhatsApp number can stay linked to at once, across every hospital."
              error={error || undefined}
            >
              <Input
                id="max_active_patient_links"
                type="number"
                min={1}
                value={maxActiveLinks}
                invalid={!!error}
                onChange={(e) => setMaxActiveLinks(e.target.value)}
              />
            </Field>
          </Card>

          <Card className="p-space-5">
            <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Menu labels</h2>
            <p className="mb-space-3 text-[12.5px] text-ink-400">
              Rename how a feature appears in every hospital&apos;s WhatsApp menu. Leave a field blank to use the
              default. Applies platform-wide — a hospital&apos;s own Settings page can no longer override this.
            </p>
            {Object.keys(settings.feature_default_labels).map((key) => (
              <Field key={key} label={FEATURE_DISPLAY_NAMES[key] || key} htmlFor={`label_${key}`}>
                <Input
                  id={`label_${key}`}
                  placeholder={settings.feature_default_labels[key] || ""}
                  value={featureLabels[key] || ""}
                  onChange={(e) => setFeatureLabel(key, e.target.value)}
                />
              </Field>
            ))}
          </Card>

          <Card className="p-space-5">
            <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">DPDP Act consent</h2>
            <p className="mb-space-3 text-[12.5px] text-ink-400">
              When enabled, a fresh conversation on ANY hospital&apos;s bot must tap &quot;I Agree&quot; on a fixed
              Digital Personal Data Protection (DPDP) Act notice right after choosing a language, before anything
              else — including registration or picking a patient. The decision is remembered per phone number, so a
              patient who has already agreed is never asked again.
            </p>
            <CheckboxRow checked={dpdpRequired} onChange={setDpdpRequired}>
              Require DPDP consent before entering the menu, for every hospital
            </CheckboxRow>
          </Card>

          {saved && <p className="text-[13px] text-success">Saved.</p>}
          <Button type="submit" disabled={saving || !maxActiveLinks} className="self-start">
            {saving ? "Saving…" : "Save"}
          </Button>
        </form>
      )}
    </div>
  );
}

export default function PlatformSettingsPage() {
  return <PlatformSettingsForm />;
}
