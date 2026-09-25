"use client";

import { Building2, Check, Sprout } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { CAPABILITY_META } from "@/lib/hospitalCapabilities";
import type { PublicPlan } from "@/hooks/usePublicPlans";

type Props = {
  plans: PublicPlan[];
  cycle: "monthly" | "annual";
  onCycleChange: (cycle: "monthly" | "annual") => void;
  onSelectPlan: (planId: number) => void;
  selectingPlanId: number | null;
  ctaLabel?: string;
};

/** The plan cards + monthly/annual toggle, shared by /plans (public,
 * informational -- src/app/plans/page.tsx) and the in-portal upgrade
 * modal (components/portal/PlanUpgradeModal.tsx). Same markup either way
 * -- only what onSelectPlan actually DOES differs between the two call
 * sites (navigate vs. really start billing), so that's the one thing left
 * to the caller rather than duplicated here. */
export function PlanPickerGrid({
  plans,
  cycle,
  onCycleChange,
  onSelectPlan,
  selectingPlanId,
  ctaLabel = "Get Started",
}: Props) {
  return (
    <div>
      <div className="mb-space-6 mx-auto flex w-fit rounded-md bg-black/4 p-1">
        <button
          type="button"
          onClick={() => onCycleChange("monthly")}
          className={cn(
            "px-space-4 py-space-2 rounded-md text-[13px] font-semibold transition-colors duration-150",
            cycle === "monthly" ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]" : "text-ink-500",
          )}
        >
          Monthly
        </button>
        <button
          type="button"
          onClick={() => onCycleChange("annual")}
          className={cn(
            "px-space-4 py-space-2 relative rounded-md text-[13px] font-semibold transition-colors duration-150",
            cycle === "annual" ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]" : "text-ink-500",
          )}
        >
          Annual
          <span className="bg-success px-space-2 absolute -top-2.5 -right-2.5 rounded-full py-0.5 text-[9.5px] font-bold tracking-wide text-white uppercase">
            Save more
          </span>
        </button>
      </div>

      <div className="gap-space-5 mx-auto grid max-w-3xl grid-cols-1 md:grid-cols-2">
        {plans.map((plan) => {
          const Icon = plan.is_popular ? Building2 : Sprout;
          const annualPrice = plan.price_monthly * 12 * (1 - plan.annual_discount_pct / 100);
          const displayPrice = cycle === "annual" ? annualPrice / 12 : plan.price_monthly;
          return (
            <Card
              key={plan.id}
              className={cn(
                "p-space-6 relative flex flex-col",
                plan.is_popular && "border-brand-300 shadow-[var(--shadow-md)]",
              )}
            >
              {plan.is_popular && (
                <span className="bg-brand-600 px-space-3 right-space-5 absolute top-0 -translate-y-1/2 rounded-full py-1 text-[10.5px] font-bold tracking-wide text-white uppercase">
                  Most Popular
                </span>
              )}
              <span className="bg-brand-50 text-brand-600 mb-space-4 flex h-11 w-11 items-center justify-center rounded-full">
                <Icon size={22} />
              </span>
              <h2 className="text-ink-900 text-[18px] font-bold">{plan.name}</h2>
              <p className="text-hint mb-space-4">{plan.description}</p>
              <div className="mb-space-1">
                <span className="text-ink-900 text-[32px] font-bold">
                  ₹{Math.round(displayPrice).toLocaleString("en-IN")}
                </span>
                <span className="text-ink-400 text-[13px]"> / month</span>
              </div>
              {cycle === "annual" && plan.annual_discount_pct > 0 ? (
                <p className="text-hint mb-space-4">
                  billed ₹{Math.round(annualPrice).toLocaleString("en-IN")} / year
                </p>
              ) : (
                <div className="mb-space-4" />
              )}
              <ul className="space-y-space-2 mb-space-6 flex-1 text-[13px]">
                {plan.capabilities.map((key) => (
                  <li key={key} className="gap-space-2 flex items-start">
                    <Check size={15} className="text-success mt-0.5 shrink-0" />
                    <span className="text-ink-700">{CAPABILITY_META[key]?.label ?? key}</span>
                  </li>
                ))}
                <li className="gap-space-2 flex items-start">
                  <Check size={15} className="text-success mt-0.5 shrink-0" />
                  <span className="text-ink-700">
                    {plan.max_users == null
                      ? "Unlimited Staff Users"
                      : `Up to ${plan.max_users} Staff Users`}
                  </span>
                </li>
              </ul>
              <button
                type="button"
                onClick={() => onSelectPlan(plan.id)}
                disabled={selectingPlanId === plan.id}
                className={cn(
                  "py-space-3 rounded-md text-[13.5px] font-semibold transition-colors duration-150 disabled:opacity-60",
                  plan.is_popular
                    ? "bg-brand-600 hover:bg-brand-700 text-white"
                    : "border-line text-ink-700 hover:bg-paper border",
                )}
              >
                {selectingPlanId === plan.id ? "Starting…" : ctaLabel}
              </button>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
