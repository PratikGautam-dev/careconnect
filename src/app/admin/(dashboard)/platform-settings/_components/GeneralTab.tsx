"use client";

import { Card } from "@/components/ui/Card";
import { CheckboxRow } from "@/components/ui/Checkbox";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";

type Props = {
  maxActiveLinks: string;
  setMaxActiveLinks: (value: string) => void;
  dpdpRequired: boolean;
  setDpdpRequired: (checked: boolean) => void;
  gstEnabled: boolean;
  setGstEnabled: (checked: boolean) => void;
  gstPercent: string;
  setGstPercent: (value: string) => void;
  platformFeeEnabled: boolean;
  setPlatformFeeEnabled: (checked: boolean) => void;
  platformFeePercent: string;
  setPlatformFeePercent: (value: string) => void;
  error: string | null;
};

export function GeneralTab({
  maxActiveLinks,
  setMaxActiveLinks,
  dpdpRequired,
  setDpdpRequired,
  gstEnabled,
  setGstEnabled,
  gstPercent,
  setGstPercent,
  platformFeeEnabled,
  setPlatformFeeEnabled,
  platformFeePercent,
  setPlatformFeePercent,
  error,
}: Props) {
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
        <h2 className="mb-space-1 text-ink-900 text-[15px] font-bold">GST &amp; platform fee</h2>
        <p className="mb-space-3 text-ink-400 text-[12.5px]">
          The default rate for every hospital, shown as separate line items on the Razorpay payment
          page and added to the total a patient pays. Switch either one off to stop charging it
          without losing the rate you last entered. A hospital running its own Razorpay account can
          pick its own rate instead, from its own tenant page. Neither is refunded on a
          cancellation, regardless of the hospital&apos;s own cancellation policy.
        </p>
        <div className="gap-x-space-4 gap-y-space-3 grid grid-cols-1 sm:grid-cols-2">
          <div>
            <div className="mb-space-2 gap-space-2 flex items-center">
              <Switch
                checked={gstEnabled}
                onChange={() => setGstEnabled(!gstEnabled)}
                aria-label="Charge GST"
              />
              <span className="text-ink-900 text-[13px] font-medium">Charge GST</span>
            </div>
            <Field label="GST (%)" htmlFor="gst_percent">
              <Input
                id="gst_percent"
                type="number"
                min={0}
                max={50}
                step="0.01"
                placeholder="0"
                disabled={!gstEnabled}
                value={gstPercent}
                onChange={(e) => setGstPercent(e.target.value)}
              />
            </Field>
          </div>
          <div>
            <div className="mb-space-2 gap-space-2 flex items-center">
              <Switch
                checked={platformFeeEnabled}
                onChange={() => setPlatformFeeEnabled(!platformFeeEnabled)}
                aria-label="Charge platform fee"
              />
              <span className="text-ink-900 text-[13px] font-medium">Charge platform fee</span>
            </div>
            <Field label="Platform fee (%)" htmlFor="platform_fee_percent">
              <Input
                id="platform_fee_percent"
                type="number"
                min={0}
                max={50}
                step="0.01"
                placeholder="0"
                disabled={!platformFeeEnabled}
                value={platformFeePercent}
                onChange={(e) => setPlatformFeePercent(e.target.value)}
              />
            </Field>
          </div>
        </div>
        <p className="mt-space-3 text-ink-900 text-[12.5px]">
          {!gstEnabled && !platformFeeEnabled ? (
            <span className="text-ink-400">
              No GST or platform fee charged -- every hospital&apos;s patients pay the fee amount
              only.
            </span>
          ) : (
            <>
              Every hospital&apos;s patients will be charged{" "}
              <span className="font-bold">
                {[
                  gstEnabled && `${gstPercent || 0}% GST`,
                  platformFeeEnabled && `${platformFeePercent || 0}% platform fee`,
                ]
                  .filter(Boolean)
                  .join(" and ")}
              </span>{" "}
              on top of the appointment fee, unless that hospital has its own rate configured.
            </>
          )}
        </p>
      </Card>

      <Card className="p-space-5">
        <h2 className="mb-space-1 text-ink-900 text-[15px] font-bold">DPDP Act consent</h2>
        <p className="mb-space-3 text-ink-400 text-[12.5px]">
          When enabled, a fresh conversation on ANY hospital&apos;s bot must tap &quot;I Agree&quot;
          on a fixed Digital Personal Data Protection (DPDP) Act notice right after choosing a
          language, before anything else — including registration or picking a patient. The decision
          is remembered per phone number, so a patient who has already agreed is never asked again.
        </p>
        <CheckboxRow checked={dpdpRequired} onChange={setDpdpRequired}>
          Require DPDP consent before entering the menu, for every hospital
        </CheckboxRow>
      </Card>
    </div>
  );
}
