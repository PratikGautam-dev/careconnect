"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";

export type CancellationTier = { hours_before: number; deduction_percent: number };

/** The IRCTC-style deduction ladder inside Settings -> Appointments' own
 * "Cancellation & Refund Policy" card -- part of the SAME usePortalSettings
 * draft/save as every other field on that tab (not an independent save like
 * LeavePolicyManager's own), since the backend already treats
 * cancellation_policy as just another hospital_settings field on the one
 * PATCH /api/portal/settings payload. Rows aren't required to stay sorted
 * while editing -- the backend sorts by hours_before descending on save. */
export function CancellationPolicyEditor({
  tiers,
  onChange,
  disabled,
}: {
  tiers: CancellationTier[];
  onChange: (tiers: CancellationTier[]) => void;
  disabled?: boolean;
}) {
  function updateTier(index: number, patch: Partial<CancellationTier>) {
    onChange(tiers.map((t, i) => (i === index ? { ...t, ...patch } : t)));
  }

  function removeTier(index: number) {
    onChange(tiers.filter((_, i) => i !== index));
  }

  function addTier() {
    onChange([...tiers, { hours_before: 0, deduction_percent: 0 }]);
  }

  return (
    <div>
      {tiers.length === 0 && (
        <p className="mb-space-3 text-ink-400 text-[12.5px]">
          No tiers configured -- a patient cancellation falls back to the platform default ladder.
        </p>
      )}
      <div className="gap-space-2 mb-space-3 flex flex-col">
        {tiers.map((tier, i) => (
          <div key={i} className="gap-space-2 flex items-start">
            <Field label={i === 0 ? "Hours before appointment" : undefined} className="mb-0 flex-1">
              <Input
                type="number"
                min={0}
                value={tier.hours_before}
                disabled={disabled}
                onChange={(e) => updateTier(i, { hours_before: Number(e.target.value) })}
              />
            </Field>
            <Field label={i === 0 ? "Deduction (%)" : undefined} className="mb-0 flex-1">
              <Input
                type="number"
                min={0}
                max={100}
                value={tier.deduction_percent}
                disabled={disabled}
                onChange={(e) => updateTier(i, { deduction_percent: Number(e.target.value) })}
              />
            </Field>
            <Button
              type="button"
              variant="secondary"
              disabled={disabled}
              onClick={() => removeTier(i)}
              className={i === 0 ? "mt-[26px]" : undefined}
              aria-label="Remove tier"
            >
              <Trash2 size={14} />
            </Button>
          </div>
        ))}
      </div>
      <Button type="button" variant="secondary" disabled={disabled} onClick={addTier}>
        <Plus size={14} /> Add tier
      </Button>
    </div>
  );
}
