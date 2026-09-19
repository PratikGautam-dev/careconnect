import { useState } from "react";
import { Compass } from "lucide-react";
import { cn } from "@/lib/cn";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import type { DataTier, WizardState } from "../types";
import type { WizardDispatch } from "../useWizardState";

const TIERS: {
  tier: DataTier;
  badge: string;
  badgeTone: "clay" | "brand";
  title: string;
  description: string;
  cta: string;
}[] = [
  {
    tier: "tier1",
    badge: "Tier 1",
    badgeTone: "clay",
    title: "Start with DAAP Booking Platform",
    description: "We don't have an appointment database or hospital booking software.",
    cta: "Select this setup",
  },
  {
    tier: "tier2",
    badge: "Tier 2",
    badgeTone: "brand",
    title: "Connect Existing Hospital Software",
    description: "We already have a website, ERP or appointment database.",
    cta: "Connect our system",
  },
  {
    tier: "tier3",
    badge: "Tier 3",
    badgeTone: "clay",
    title: "Activate with DAAP Hospital ERP",
    description: "We already use a website and hospital ERP from DAAPrime Technologies.",
    cta: "Activate WhatsApp booking",
  },
];

type Props = { state: WizardState; dispatch: WizardDispatch };

export function Step0DataConnection({ state, dispatch }: Props) {
  const [showRecommendation, setShowRecommendation] = useState(false);

  function selectTier(tier: DataTier) {
    dispatch({ type: "set", field: "dataTier", value: tier });
  }

  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step 0 of 9</p>
      <h2 className="text-display mb-space-2">0. Choose your hospital setup</h2>
      <p className="text-body mb-space-5">
        Select the option that best describes your current setup. We&apos;ll customize the rest of this wizard
        around it.
      </p>

      <div className="mb-space-5 grid grid-cols-1 gap-space-4 md:grid-cols-3">
        {TIERS.map(({ tier, badge, badgeTone, title, description, cta }) => {
          const selected = state.dataTier === tier;
          return (
            <div
              key={tier}
              className={cn(
                "flex flex-col rounded-lg border bg-card p-space-4 text-center shadow-[var(--shadow-sm)] transition-all duration-150 ease-(--ease-standard)",
                selected ? "border-brand-400 ring-2 ring-brand-100" : "border-line",
              )}
            >
              <h3 className="mb-space-2 text-[16px] leading-snug font-bold text-ink-900">{title}</h3>
              <p className="mb-space-3 text-[13px] leading-relaxed text-ink-600">{description}</p>
              <span
                className={cn(
                  "mx-auto mb-space-4 rounded-full px-space-3 py-1 text-[11px] font-bold tracking-wide uppercase",
                  badgeTone === "brand" ? "bg-brand-50 text-brand-700" : "bg-clay-100 text-clay-700",
                )}
              >
                {badge}
              </span>
              <button
                type="button"
                onClick={() => selectTier(tier)}
                className="mt-auto rounded-md bg-brand-600 px-space-3 py-space-2 text-[13.5px] font-semibold text-white shadow-[var(--shadow-sm)] transition-colors duration-150 hover:bg-brand-700 active:bg-brand-800"
              >
                {cta}
              </button>
            </div>
          );
        })}
      </div>

      <p className="mb-space-4 text-center text-[12.5px] font-semibold tracking-wide text-ink-400 uppercase">OR</p>

      <div className="mb-space-5 rounded-lg border border-line bg-paper p-space-5">
        <div className="flex flex-col items-center gap-space-3 text-center md:flex-row md:text-left">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
            <Compass size={20} strokeWidth={2} />
          </div>
          <div className="flex-1">
            <h4 className="text-[14.5px] font-bold text-ink-900">Help me choose</h4>
            <p className="text-[13px] text-ink-600">Answer a few questions and we&apos;ll recommend the best setup for you.</p>
          </div>
        </div>
        <div className="mt-space-4 flex flex-col items-center gap-space-2">
          <button
            type="button"
            onClick={() => {
              selectTier("tier1");
              setShowRecommendation(true);
            }}
            className="rounded-md bg-clay-100 px-space-4 py-space-2 text-[13.5px] font-semibold text-clay-700 transition-colors duration-150 hover:bg-clay-100/70"
          >
            Find my setup
          </button>
          {showRecommendation && (
            <p className="text-[12.5px] leading-relaxed text-ink-600">
              Most hospitals should pick <strong className="text-ink-900">Tier 1</strong> — it works immediately
              with no extra setup. We&apos;ve selected it for you; only switch to Tier 2 or 3 if a separate system
              already owns your doctors&apos; schedules today.
            </p>
          )}
        </div>
      </div>

      {state.dataTier === "tier2" && (
        <div className="mb-space-5 grid grid-cols-1 gap-space-4 rounded-lg border border-line bg-paper p-space-4 md:grid-cols-2">
          <Field label="API base URL" htmlFor="api_base_url" required>
            <Input
              id="api_base_url"
              placeholder="https://api.yourhospital.example"
              value={state.apiBaseUrl}
              onChange={(e) => dispatch({ type: "set", field: "apiBaseUrl", value: e.target.value })}
            />
          </Field>
          <Field label="API key" htmlFor="api_key" required>
            <Input
              id="api_key"
              value={state.apiKey}
              onChange={(e) => dispatch({ type: "set", field: "apiKey", value: e.target.value })}
            />
          </Field>
        </div>
      )}

      {state.dataTier === "tier3" && (
        <div className="mb-space-5 rounded-lg border border-clay-300 bg-clay-100/40 p-space-4 text-[13.5px] leading-relaxed text-ink-600">
          Direct database connection is not self-serve — it requires a secure/VPN-reachable connection and a
          scoped-down database user, set up as a manually-assisted engagement. No fields to fill in here; we&apos;ll
          be in touch to arrange it after you submit.
        </div>
      )}
    </div>
  );
}

export function validateStep0(state: WizardState): string | null {
  if (state.dataTier === "tier2" && (!state.apiBaseUrl.trim() || !state.apiKey.trim())) {
    return "API base URL and API key are both required for Tier 2.";
  }
  return null;
}
