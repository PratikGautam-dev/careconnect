"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { PlanPickerGrid } from "@/components/plans/PlanPickerGrid";
import { usePublicPlans } from "@/hooks/usePublicPlans";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** The REAL "select a plan and start billing" flow -- opened from
 * SubscriptionGate.tsx's blocked screen (admin-capable staff only; see
 * that component for why non-admins never see the button that opens
 * this). Same plan cards /plans (public, informational-only) shows, via
 * the shared PlanPickerGrid, but selecting one HERE actually calls the
 * billing-start endpoint -- this modal lives inside the portal's real
 * authenticated session (StaffSessionProvider already wraps
 * app/portal/layout.tsx), unlike /plans, which is deliberately outside
 * that tree so it stays reachable by a visitor who's never logged in. */
export function PlanUpgradeModal({ open, onOpenChange }: Props) {
  const { plans, error } = usePublicPlans();
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");
  const [startingPlanId, setStartingPlanId] = useState<number | null>(null);

  async function handleSelectPlan(planId: number) {
    setStartingPlanId(planId);
    try {
      const result = await staffFetch("/api/portal/settings/billing/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, billing_cycle: cycle }),
      });
      if (!result.ok) {
        if (!result.unauthorized) toast.error("Couldn't start billing", result.error);
        return;
      }
      const checkoutUrl = (result.data as { checkout_url?: string }).checkout_url;
      if (checkoutUrl) {
        // Same-tab navigation -- Razorpay's redirect_url
        // (modules/razorpay_subscriptions.py) sends the browser straight
        // back to /portal/dashboard once checkout finishes, so leaving in
        // this tab is what makes that redirect land somewhere meaningful
        // instead of a second, orphaned tab.
        window.location.href = checkoutUrl;
      }
    } finally {
      setStartingPlanId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="scrollbar-hide min-h-screen w-[calc(100%)] max-w-none rounded-none">
        <div className="text-center">
          <DialogTitle>Upgrade your plan</DialogTitle>
          <p className="text-hint mb-space-6">Choose a plan to activate this hospital.</p>
        </div>
        {error && <p className="text-error mb-space-4 text-[13px]">{error}</p>}

        {!plans ? (
          <p className="text-ink-400 text-[13px]">Loading…</p>
        ) : (
          <PlanPickerGrid
            plans={plans}
            cycle={cycle}
            onCycleChange={setCycle}
            onSelectPlan={handleSelectPlan}
            selectingPlanId={startingPlanId}
            ctaLabel="Get Started"
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
