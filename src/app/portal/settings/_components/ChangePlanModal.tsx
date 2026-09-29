"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { PlanPickerGrid } from "@/components/plans/PlanPickerGrid";
import { usePublicPlans } from "@/hooks/usePublicPlans";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentPlanId: number | null;
  onSelectPlan: (planId: number, billingCycle: "monthly" | "annual") => Promise<boolean>;
  changing: boolean;
};

/** Settings -> Billing's "Upgrade Plan" button -- the ALREADY-subscribed
 * counterpart to PlanUpgradeModal.tsx (that one is for a hospital with no
 * subscription yet, opened from SubscriptionGate's blocked screen, and
 * calls the billing-start endpoint). This one calls change-plan instead,
 * which reuses the hospital's already-authorized payment method (no
 * re-checkout) and takes effect at the next renewal date -- see
 * useBillingSubscription.ts's changePlan() and portal/routes/
 * billing_subscription.py's own change_plan() docstring. Same
 * PlanPickerGrid/usePublicPlans as PlanUpgradeModal -- only what
 * onSelectPlan actually calls differs between the two. */
export function ChangePlanModal({ open, onOpenChange, currentPlanId, onSelectPlan, changing }: Props) {
  const { plans, error } = usePublicPlans();
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");
  const [selectingPlanId, setSelectingPlanId] = useState<number | null>(null);

  async function handleSelectPlan(planId: number) {
    setSelectingPlanId(planId);
    try {
      const ok = await onSelectPlan(planId, cycle);
      if (ok) onOpenChange(false);
    } finally {
      setSelectingPlanId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="scrollbar-hide min-h-screen w-[calc(100%)] max-w-none rounded-none">
        <div className="text-center">
          <DialogTitle>Upgrade your plan</DialogTitle>
          <p className="text-hint mb-space-6">
            Takes effect at your next renewal date -- your current cycle finishes at today&apos;s
            price.
          </p>
        </div>
        {error && <p className="text-error mb-space-4 text-[13px]">{error}</p>}

        {!plans ? (
          <p className="text-ink-400 text-[13px]">Loading…</p>
        ) : (
          <PlanPickerGrid
            plans={plans.filter((p) => p.id !== currentPlanId)}
            cycle={cycle}
            onCycleChange={setCycle}
            onSelectPlan={handleSelectPlan}
            selectingPlanId={changing ? selectingPlanId : null}
            ctaLabel="Switch to this plan"
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
