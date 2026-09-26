"use client";

import { Card } from "@/components/ui/Card";
import { CheckboxRow } from "@/components/ui/Checkbox";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";

type Props = {
  maxActiveLinks: string;
  setMaxActiveLinks: (value: string) => void;
  dpdpRequired: boolean;
  setDpdpRequired: (checked: boolean) => void;
  error: string | null;
};

export function GeneralTab({ maxActiveLinks, setMaxActiveLinks, dpdpRequired, setDpdpRequired, error }: Props) {
  return (
    <div className="gap-space-5 flex flex-col">
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
        <h2 className="mb-space-1 text-ink-900 text-[15px] font-bold">DPDP Act consent</h2>
        <p className="mb-space-3 text-ink-400 text-[12.5px]">
          When enabled, a fresh conversation on ANY hospital&apos;s bot must tap &quot;I Agree&quot;
          on a fixed Digital Personal Data Protection (DPDP) Act notice right after choosing a
          language, before anything else — including registration or picking a patient. The
          decision is remembered per phone number, so a patient who has already agreed is never
          asked again.
        </p>
        <CheckboxRow checked={dpdpRequired} onChange={setDpdpRequired}>
          Require DPDP consent before entering the menu, for every hospital
        </CheckboxRow>
      </Card>
    </div>
  );
}
