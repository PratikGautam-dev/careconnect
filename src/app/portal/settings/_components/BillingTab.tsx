"use client";

import { useState } from "react";
import { CreditCard, ExternalLink, Users } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { useBillingSubscription } from "@/hooks/useBillingSubscription";
import { cn } from "@/lib/cn";
import { SectionHeader } from "./settings-ui";

const STATUS_LABEL: Record<string, string> = {
  unassigned: "No Plan Assigned",
  trial: "Trial",
  authorization_pending: "Awaiting Payment Setup",
  active: "Active",
  renewal_due: "Renewal Due",
  expired: "Expired",
  cancelled: "Cancelled",
};
const STATUS_TONE: Record<string, "success" | "clay" | "neutral" | "brand"> = {
  unassigned: "neutral",
  trial: "brand",
  authorization_pending: "clay",
  active: "success",
  renewal_due: "clay",
  expired: "clay",
  cancelled: "neutral",
};

// Mirrors admin/subscriptions_api.py's _NON_TERMINAL_STATUSES exactly --
// razorpay_subscription_id stays set forever as history even after the
// real subscription is cancelled/expired, so "is billing currently live"
// is id-set AND status still non-terminal, not id-set alone.
const LIVE_BILLING_STATUSES = new Set(["authorization_pending", "active", "renewal_due"]);

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Settings -> Billing: the hospital's own CareConnect subscription --
 * self-serve payment setup and plan changes, wired to
 * portal/routes/billing_subscription.py. A super admin only ASSIGNS which
 * plan a hospital is on (/admin/subscriptions) -- this tab is where that
 * assignment actually gets paid for, and stays the single place a hospital
 * admin manages their own billing (upgrade/downgrade, see current status). */
export function BillingTab() {
  const { data, error, startBilling, changePlan, starting, changingPlan } =
    useBillingSubscription();
  const [changingTo, setChangingTo] = useState<string>("");
  const [pickedPlanId, setPickedPlanId] = useState<string>("");
  const [pickedCycle, setPickedCycle] = useState<"monthly" | "annual">("monthly");

  if (error) return <p className="text-error text-[13px]">{error}</p>;
  if (!data) return <p className="text-ink-400 text-[13px]">Loading…</p>;

  const {
    subscription,
    plan,
    available_plans: availablePlans,
    billing_configured: billingConfigured,
    seats_used: seatsUsed,
    bookings_used: bookingsUsed,
  } = data;

  async function handleStartFresh() {
    if (!pickedPlanId) return;
    const checkoutUrl = await startBilling(Number(pickedPlanId), pickedCycle);
    // Same-tab -- Razorpay's redirect_url sends this tab straight back to
    // /portal/dashboard once checkout finishes.
    if (checkoutUrl) window.location.href = checkoutUrl;
  }

  if (!subscription) {
    return (
      <Card className="p-space-5">
        <SectionHeader
          icon={CreditCard}
          tint="brand"
          title="Get Started"
          subtitle="Choose a plan for this hospital."
        />
        <p className="text-hint mb-space-3">
          No plan is set up yet -- pick one below to start billing. You&apos;ll be taken to a secure
          Razorpay checkout to authorize payment.
        </p>
        {!billingConfigured ? (
          <p className="text-error text-[12.5px]">
            Billing isn&apos;t configured on the server yet.
          </p>
        ) : (
          <div className="gap-space-3 flex flex-wrap items-end">
            <select
              value={pickedPlanId}
              onChange={(e) => setPickedPlanId(e.target.value)}
              className="border-line bg-card px-space-3 text-ink-900 h-10 min-w-52 rounded-md border text-[13px]"
            >
              <option value="">Select a plan…</option>
              {availablePlans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} (₹{p.price_monthly.toLocaleString("en-IN")}/mo)
                </option>
              ))}
            </select>
            <select
              value={pickedCycle}
              onChange={(e) => setPickedCycle(e.target.value as "monthly" | "annual")}
              className="border-line bg-card px-space-3 text-ink-900 h-10 rounded-md border text-[13px]"
            >
              <option value="monthly">Monthly</option>
              <option value="annual">Annual</option>
            </select>
            <button
              type="button"
              onClick={handleStartFresh}
              disabled={!pickedPlanId || starting}
              className="bg-brand-600 hover:bg-brand-700 px-space-4 h-10 rounded-md text-[13px] font-semibold text-white disabled:opacity-60"
            >
              {starting ? "Starting…" : "Start Billing"}
            </button>
          </div>
        )}
      </Card>
    );
  }

  const status = subscription.status;
  const cycleLabel = subscription.billing_cycle === "annual" ? "Annual" : "Monthly";

  async function handleStart() {
    if (!plan || !subscription) return;
    const checkoutUrl = await startBilling(
      plan.id,
      (subscription.billing_cycle ?? "monthly") as "monthly" | "annual",
    );
    if (checkoutUrl) window.location.href = checkoutUrl;
  }

  async function handleChangePlan() {
    if (!changingTo || !subscription) return;
    const ok = await changePlan(
      Number(changingTo),
      (subscription.billing_cycle ?? "monthly") as "monthly" | "annual",
    );
    if (ok) setChangingTo("");
  }

  return (
    <div className="space-y-space-4">
      <Card className="p-space-5">
        <SectionHeader
          icon={CreditCard}
          tint="brand"
          title="Current Plan"
          subtitle="Your CareConnect subscription."
        />

        <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2">
          <div>
            <p className="text-hint mb-1">Plan</p>
            <p className="text-ink-900 text-[15px] font-bold">{plan?.name ?? "—"}</p>
            {plan && (
              <p className="text-hint mt-0.5">
                ₹{plan.price_monthly.toLocaleString("en-IN")} / month, billed{" "}
                {cycleLabel.toLowerCase()}
              </p>
            )}
          </div>
          <div>
            <p className="text-hint mb-1">Status</p>
            <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>
          </div>
          <div>
            <p className="text-hint mb-1">Renewal Date</p>
            <p className="text-ink-900 text-[13.5px] font-semibold">
              {formatDate(subscription.renewal_date)}
            </p>
          </div>
          <div>
            <p className="text-hint mb-1">Payment Status</p>
            <p className="text-ink-900 text-[13.5px] font-semibold capitalize">
              {subscription.payment_status ?? "—"}
            </p>
          </div>
        </div>

        {plan && (
          <div className="gap-space-4 border-line mt-space-4 pt-space-4 grid grid-cols-1 border-t sm:grid-cols-2">
            <div>
              <p className="text-hint mb-1">Staff Users</p>
              <p className="text-ink-900 text-[13.5px] font-semibold">
                {plan.max_users == null ? "Unlimited" : `${seatsUsed} / ${plan.max_users}`}
              </p>
            </div>
            <div>
              <p className="text-hint mb-1">Bookings this period</p>
              <p className="text-ink-900 text-[13.5px] font-semibold">
                {plan.max_bookings == null ? "Unlimited" : `${bookingsUsed} / ${plan.max_bookings}`}
              </p>
              {plan.max_bookings != null && (
                <div className="bg-paper mt-space-2 h-1.5 w-full overflow-hidden rounded-full">
                  <div
                    className={cn(
                      "h-full rounded-full transition-[width] duration-300",
                      bookingsUsed >= plan.max_bookings ? "bg-error" : "bg-brand-600",
                    )}
                    style={{ width: `${Math.min(100, (bookingsUsed / plan.max_bookings) * 100)}%` }}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {status === "authorization_pending" && (
          <div className="border-line mt-space-4 pt-space-4 border-t">
            <p className="text-hint mb-space-2">
              Payment setup hasn&apos;t been completed yet. Finish authorizing your payment method
              to activate this plan.
            </p>
            {!billingConfigured ? (
              <p className="text-error text-[12.5px]">
                Billing isn&apos;t configured on the server yet.
              </p>
            ) : subscription.razorpay_short_url ? (
              <a
                href={subscription.razorpay_short_url}
                className="bg-brand-600 hover:bg-brand-700 gap-space-2 px-space-4 inline-flex h-10 items-center rounded-md text-[13px] font-semibold text-white"
              >
                <ExternalLink size={14} /> Complete Payment Setup
              </a>
            ) : null}
          </div>
        )}

        {/* "No live Razorpay subscription yet" is razorpay_subscription_id
        AND status still non-terminal -- NOT razorpay_subscription_id alone.
        A super admin can set status to Active/Renewal Due/etc. purely as a
        record-keeping label without real billing existing yet (gating on
        status === "trial" alone left an Active-but-unbilled hospital with
        no way to start real billing), AND the id sticks around forever as
        history even after a real subscription is cancelled/expired (the
        webhook never clears it) -- gating on id-alone left a hospital that
        already cancelled with no way to ever start billing again. Mirrors
        admin/subscriptions_api.py's _NON_TERMINAL_STATUSES exactly. */}
        {!(subscription.razorpay_subscription_id && LIVE_BILLING_STATUSES.has(status)) &&
          status !== "authorization_pending" &&
          plan && (
            <div className="border-line mt-space-4 pt-space-4 border-t">
              <p className="text-hint mb-space-2">
                {status === "trial"
                  ? "Set up real billing to keep this plan active after your trial."
                  : "No payment method is on file yet for this plan -- set one up to start real billing."}
              </p>
              {!billingConfigured ? (
                <p className="text-error text-[12.5px]">
                  Billing isn&apos;t configured on the server yet.
                </p>
              ) : (
                <button
                  type="button"
                  onClick={handleStart}
                  disabled={starting}
                  className="bg-brand-600 hover:bg-brand-700 px-space-4 h-10 rounded-md text-[13px] font-semibold text-white disabled:opacity-60"
                >
                  {starting ? "Starting…" : "Start Billing"}
                </button>
              )}
            </div>
          )}
      </Card>

      {/* Change Plan only makes sense once a real Razorpay subscription
      exists to move to a different plan on -- the backend itself refuses
      (409) an attempt while razorpay_subscription_id is unset, even if
      status happens to be "active" from a manual assignment. */}
      {subscription.razorpay_subscription_id &&
        (status === "active" || status === "renewal_due") && (
          <Card className="p-space-5">
            <SectionHeader
              icon={Users}
              tint="success"
              title="Change Plan"
              subtitle="Takes effect at your next renewal date -- your current cycle finishes at today's price."
            />
            <div className="gap-space-3 flex flex-wrap items-end">
              <select
                value={changingTo}
                onChange={(e) => setChangingTo(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 h-10 min-w-52 rounded-md border text-[13px]"
              >
                <option value="">Select a plan…</option>
                {availablePlans
                  .filter((p) => p.id !== plan?.id)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} (₹{p.price_monthly.toLocaleString("en-IN")}/mo)
                    </option>
                  ))}
              </select>
              <button
                type="button"
                onClick={handleChangePlan}
                disabled={!changingTo || changingPlan}
                className="border-line text-ink-700 px-space-4 hover:bg-paper h-10 rounded-md border text-[13px] font-semibold disabled:opacity-50"
              >
                {changingPlan ? "Scheduling…" : "Schedule Change"}
              </button>
            </div>
          </Card>
        )}
    </div>
  );
}
