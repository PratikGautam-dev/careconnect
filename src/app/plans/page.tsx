"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BrandMark } from "@/components/marketing/BrandMark";
import { PlanPickerGrid } from "@/components/plans/PlanPickerGrid";
import { useStaffSession } from "@/lib/staffAuth";
import { usePublicPlans } from "@/hooks/usePublicPlans";

/** Public, unauthenticated, informational-only plan browser -- reachable
 * by anyone (never onboarded, logged out, or a logged-in hospital admin
 * just browsing). Deliberately does NOT start billing from here -- "Get
 * Started" only ever navigates:
 *   - not logged in -> /portal/login
 *   - logged in -> /portal/dashboard, where a blocked hospital sees
 *     SubscriptionGate's takeover, and an admin-capable staff member
 *     opens the REAL plan picker from there (components/portal/
 *     PlanUpgradeModal.tsx) -- that modal is the only place a plan
 *     selection actually calls the billing-start endpoint, since it
 *     lives inside the portal's real, authenticated session context
 *     (this page structurally can't reuse that context -- it's outside
 *     app/portal/layout.tsx's StaffSessionProvider on purpose, so it
 *     stays reachable by a visitor who has never logged in at all). */
export default function PublicPlansPage() {
  const router = useRouter();
  const session = useStaffSession();
  const { plans, error } = usePublicPlans();
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");

  function handleGetStarted() {
    router.push(session ? "/portal/dashboard" : "/portal/login");
  }

  return (
    <>
      <header className="gap-space-3 border-line bg-paper/90 px-space-4 py-space-4 md:px-space-7 lg:px-space-9 sticky top-0 z-10 flex items-center justify-between border-b backdrop-blur-sm">
        <BrandMark />
        <Link href="/" className="text-brand-600 text-[13.5px] font-semibold hover:underline">
          Back to home
        </Link>
      </header>

      <main className="px-space-4 py-space-9 md:px-space-7 lg:px-space-9 mx-auto max-w-[1080px]">
        <div className="mb-space-8 text-center">
          <p className="text-eyebrow mb-space-2">Plans</p>
          <h1 className="text-display-lg mb-space-3">Choose a plan for your hospital</h1>
          <p className="text-hint mx-auto max-w-md">
            Flexible plans for hospitals of all sizes. Switch or cancel any time.
          </p>
        </div>

        {error && <p className="text-error mb-space-4 text-center text-[13px]">{error}</p>}

        {!plans ? (
          <p className="text-ink-400 text-center text-[13px]">Loading…</p>
        ) : (
          <PlanPickerGrid
            plans={plans}
            cycle={cycle}
            onCycleChange={setCycle}
            onSelectPlan={handleGetStarted}
            selectingPlanId={null}
            ctaLabel="Get Started"
          />
        )}
      </main>
    </>
  );
}
