"use client";

import { useState } from "react";
import { CreditCard, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useBillingSubscription, type SubscriptionPayment } from "@/hooks/useBillingSubscription";
import { cn } from "@/lib/cn";
import { formatINR } from "@/lib/formatCurrency";
import { SectionHeader } from "./settings-ui";
import { ChangePlanModal } from "./ChangePlanModal";

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

const PAYMENT_STATUS_LABEL: Record<string, string> = {
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
  expired: "Expired",
  pay_at_hospital: "Pay at Hospital",
};
const PAYMENT_STATUS_TONE: Record<string, "success" | "clay" | "neutral" | "brand"> = {
  paid: "success",
  pending: "clay",
  failed: "clay",
  expired: "neutral",
  pay_at_hospital: "neutral",
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

function PaymentHistoryRow({
  payment,
  onViewInvoice,
}: {
  payment: SubscriptionPayment;
  onViewInvoice: (paymentId: number) => void;
}) {
  return (
    <tr className="border-line border-t">
      <td className="py-space-3 text-ink-900 text-[13px]">
        {formatDate(payment.paid_at ?? payment.created_at)}
      </td>
      <td className="py-space-3 text-ink-900 text-[13px] font-semibold">
        {formatINR(payment.amount)}
      </td>
      <td className="py-space-3">
        <Badge tone={PAYMENT_STATUS_TONE[payment.status] ?? "neutral"}>
          {PAYMENT_STATUS_LABEL[payment.status] ?? payment.status}
        </Badge>
      </td>
      <td className="py-space-3 text-right">
        {payment.invoice_short_url ? (
          <a
            href={payment.invoice_short_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-600 text-[12.5px] font-semibold hover:underline"
          >
            View
          </a>
        ) : payment.status === "paid" ? (
          // Paid, but its hosted page isn't stored yet (a charge recorded
          // before invoice capture, or whose invoice.paid event never
          // arrived) -- resolved once from Razorpay on click, then saved.
          <button
            type="button"
            onClick={() => onViewInvoice(payment.id)}
            className="text-brand-600 text-[12.5px] font-semibold hover:underline"
          >
            View
          </button>
        ) : (
          // A failed/pending charge has no invoice to open -- greyed out
          // rather than hidden, so it's clear the column exists.
          <span
            className="text-ink-300 cursor-not-allowed text-[12.5px] font-semibold"
            title="No invoice available for this charge"
          >
            View
          </span>
        )}
      </td>
    </tr>
  );
}

/** Settings -> Billing: the hospital's own CareConnect subscription --
 * self-serve payment setup and plan changes, wired to
 * portal/routes/billing_subscription.py. A super admin only ASSIGNS which
 * plan a hospital is on (/admin/subscriptions) -- this tab is where that
 * assignment actually gets paid for, and stays the single place a hospital
 * admin manages their own billing (upgrade/downgrade, see current status). */
export function BillingTab() {
  const {
    data,
    error,
    startBilling,
    changePlan,
    cancelBilling,
    starting,
    changingPlan,
    cancelling,
    history,
    lastPaidCard,
    viewHistoryInvoice,
  } = useBillingSubscription();
  const [pickedPlanId, setPickedPlanId] = useState<string>("");
  const [pickedCycle, setPickedCycle] = useState<"monthly" | "annual">("monthly");
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);

  if (error) return <p className="text-error text-[13px]">{error}</p>;
  if (!data) return <p className="text-ink-400 text-[13px]">Loading…</p>;

  const {
    subscription,
    plan,
    available_plans: availablePlans,
    billing_configured: billingConfigured,
    seats_used: seatsUsed,
    bookings_used: bookingsUsed,
    bookings_reset_on: bookingsResetOn,
  } = data;

  async function handleStartFresh() {
    if (!pickedPlanId) return;
    const checkoutUrl = await startBilling(Number(pickedPlanId), pickedCycle);
    // New tab -- Razorpay's Subscriptions checkout has no redirect_url
    // support, so this keeps the portal tab open/usable during checkout.
    if (checkoutUrl) window.open(checkoutUrl, "_blank", "noopener,noreferrer");
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
                  {p.name} ({formatINR(p.price_monthly)}/mo)
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
  const isLiveBilled = !!(
    subscription.razorpay_subscription_id && LIVE_BILLING_STATUSES.has(status)
  );

  async function handleStart() {
    if (!plan || !subscription) return;
    const checkoutUrl = await startBilling(
      plan.id,
      (subscription.billing_cycle ?? "monthly") as "monthly" | "annual",
    );
    if (checkoutUrl) window.open(checkoutUrl, "_blank", "noopener,noreferrer");
  }

  async function handleUpgradeSelect(planId: number, billingCycle: "monthly" | "annual") {
    return changePlan(planId, billingCycle);
  }

  async function handleCancel() {
    setConfirmingCancel(false);
    await cancelBilling();
  }

  return (
    <div className="space-y-space-4">
      <Card className="p-space-5">
        <div className="mb-space-4 flex items-start justify-between">
          <SectionHeader
            icon={CreditCard}
            tint="brand"
            title="Current Plan"
            subtitle="Your CareConnect subscription."
          />
          {isLiveBilled && (
            <div className="gap-space-2 flex shrink-0 items-center">
              {plan && (
                <button
                  type="button"
                  onClick={() => setUpgradeOpen(true)}
                  className="border-line text-ink-700 px-space-3 hover:bg-paper h-9 shrink-0 rounded-md border text-[12.5px] font-semibold"
                >
                  Change Plan
                </button>
              )}
              {/* Opens the ConfirmDialog below, which carries the full
                  "stops future charges, access continues this cycle"
                  explanation. */}
              <button
                type="button"
                onClick={() => setConfirmingCancel(true)}
                disabled={cancelling}
                className="border-error/40 text-error hover:bg-error/5 px-space-3 h-9 shrink-0 rounded-md border text-[12.5px] font-semibold disabled:opacity-60"
              >
                {cancelling ? "Cancelling…" : "Cancel Plan"}
              </button>
            </div>
          )}
        </div>

        <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2">
          <div>
            <p className="text-hint mb-1">Plan</p>
            <p className="text-ink-900 text-[15px] font-bold">{plan?.name ?? "—"}</p>
            {plan && (
              <p className="text-hint mt-0.5">
                {formatINR(plan.price_monthly)} / month, billed {cycleLabel.toLowerCase()}
              </p>
            )}
          </div>
          <div>
            <p className="text-hint mb-1">Status</p>
            <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>
          </div>
          <div>
            <p className="text-hint mb-1">Start Date</p>
            <p className="text-ink-900 text-[13.5px] font-semibold">
              {formatDate(subscription.start_date)}
            </p>
          </div>
          <div>
            <p className="text-hint mb-1">Renewal Date</p>
            <p className="text-ink-900 text-[13.5px] font-semibold">
              {formatDate(subscription.renewal_date)}
            </p>
          </div>
        </div>

        {plan && (
          <div className="gap-space-4 border-line mt-space-4 pt-space-4 grid grid-cols-1 border-t sm:grid-cols-2">
            <div>
              <p className="text-hint mb-1">Doctors &amp; Staff</p>
              <p className="text-ink-900 text-[13.5px] font-semibold">
                {plan.max_users == null ? "Unlimited" : `${seatsUsed} / ${plan.max_users}`}
              </p>
              <p className="text-hint mt-0.5">
                Deactivating someone doesn&apos;t free a slot — deleting does.
              </p>
            </div>
            <div>
              <p className="text-hint mb-1">Bookings this month</p>
              <p className="text-ink-900 text-[13.5px] font-semibold">
                {plan.max_bookings == null ? "Unlimited" : `${bookingsUsed} / ${plan.max_bookings}`}
              </p>
              {plan.max_bookings != null && bookingsUsed >= plan.max_bookings && (
                <p className="text-error mt-0.5 text-[12px]">
                  Limit reached — new bookings are paused
                  {bookingsResetOn ? ` until ${formatDate(bookingsResetOn)}` : ""}.
                </p>
              )}
              {bookingsResetOn && (
                <p className="text-hint mt-0.5">Resets on {formatDate(bookingsResetOn)}</p>
              )}
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
                target="_blank"
                rel="noopener noreferrer"
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
        {!isLiveBilled && status !== "authorization_pending" && plan && (
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

      {isLiveBilled && (
        <Card className="p-space-5">
          <SectionHeader
            icon={CreditCard}
            tint="success"
            title="Payment"
            subtitle="The card Razorpay charges for this subscription."
          />
          {lastPaidCard?.card_last4 ? (
            <div className="border-line bg-paper px-space-4 py-space-3 flex items-center gap-3 rounded-md border">
              <span className="bg-card border-line flex h-8 w-11 shrink-0 items-center justify-center rounded border text-[10px] font-bold tracking-wide">
                {lastPaidCard.card_network?.toUpperCase() ?? "CARD"}
              </span>
              <p className="text-ink-900 text-[13.5px] font-semibold">
                {lastPaidCard.card_network ?? "Card"} •••• {lastPaidCard.card_last4}
              </p>
            </div>
          ) : (
            <p className="text-ink-400 text-[13px]">
              No card details on file yet -- these appear here after your first successful charge.
            </p>
          )}
        </Card>
      )}

      {isLiveBilled && (
        <Card className="p-space-5">
          <SectionHeader
            icon={CreditCard}
            tint="clay"
            title="Invoices"
            subtitle="Every charge recorded against this subscription."
          />
          {!history ? (
            <p className="text-ink-400 text-[13px]">Loading…</p>
          ) : history.length === 0 ? (
            <p className="text-ink-400 text-[13px]">No charges recorded yet.</p>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th className="text-hint pb-space-2 font-semibold">Date</th>
                  <th className="text-hint pb-space-2 font-semibold">Total</th>
                  <th className="text-hint pb-space-2 font-semibold">Status</th>
                  <th className="text-hint pb-space-2 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {history.map((payment) => (
                  <PaymentHistoryRow
                    key={payment.id}
                    payment={payment}
                    onViewInvoice={(id) => void viewHistoryInvoice(id)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {plan && (
        <ChangePlanModal
          open={upgradeOpen}
          onOpenChange={setUpgradeOpen}
          currentPlanId={plan.id}
          onSelectPlan={handleUpgradeSelect}
          changing={changingPlan}
        />
      )}

      <ConfirmDialog
        open={confirmingCancel}
        title="Cancel plan?"
        message="This stops future charges for this hospital's CareConnect subscription. Your team keeps access through what you've already paid for in the current cycle."
        confirmLabel="Cancel Plan"
        destructive
        busy={cancelling}
        onConfirm={handleCancel}
        onCancel={() => setConfirmingCancel(false)}
      />
    </div>
  );
}
