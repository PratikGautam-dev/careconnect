import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export type SubscriptionStatus =
  | "unassigned"
  | "trial"
  | "authorization_pending"
  | "active"
  | "renewal_due"
  | "expired"
  | "cancelled";

export type BillingSubscription = {
  hospital_id: number;
  plan_id: number | null;
  billing_cycle: "monthly" | "annual" | null;
  status: SubscriptionStatus;
  payment_status: "paid" | "pending" | "failed" | null;
  start_date: string | null;
  renewal_date: string | null;
  razorpay_subscription_id: string | null;
  razorpay_short_url: string | null;
};

export type BillingPlan = {
  id: number;
  name: string;
  description: string | null;
  price_monthly: number;
  annual_discount_pct: number;
  capabilities: string[];
  max_users: number | null;
  max_bookings: number | null;
};

export type AvailablePlan = { id: number; name: string; price_monthly: number };

export type SubscriptionPayment = {
  id: number;
  amount: number;
  currency: string;
  status: "pending" | "paid" | "failed" | "expired" | "pay_at_hospital";
  // Best-effort -- both null for a non-card charge (UPI/netbanking) or a
  // charge recorded before this capture existed (db.record_subscription_
  // payment()'s own docstring).
  card_last4: string | null;
  card_network: string | null;
  // Razorpay's own hosted invoice page for this charge -- null whenever
  // Razorpay's Invoices feature isn't enabled for the account, which is
  // the common case (db.list_subscription_payments()'s own docstring).
  // "View" only ever shows for a row where this is set.
  invoice_short_url: string | null;
  created_at: string;
  paid_at: string | null;
};

export type BillingData = {
  subscription: BillingSubscription | null;
  plan: BillingPlan | null;
  available_plans: AvailablePlan[];
  billing_configured: boolean;
  seats_used: number;
  bookings_used: number;
};

const BILLING_QUERY_KEY = ["portal-billing-subscription"] as const;
const BILLING_HISTORY_QUERY_KEY = ["portal-billing-history"] as const;

/** The hospital's own CareConnect subscription -- Settings -> Billing. A
 * DIFFERENT concept from /portal/billing's patient-payments ledger: this is
 * the hospital paying CareConnect, not a patient paying the hospital.
 * `subscription: null` means no plan assignment exists yet -- fully
 * self-serve from here: startBilling(planId, cycle) both picks the plan AND
 * creates the row (db/repositories/subscriptions.py's start_billing()
 * inserts when no row exists yet), so a hospital doesn't have to wait on a
 * super admin to assign one from /admin/subscriptions first. */
export function useBillingSubscription() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, error, refetch } = useQuery({
    queryKey: BILLING_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/settings/billing");
      return unwrapPortalResult<BillingData>(router, result);
    },
  });

  const startMutation = useMutation({
    mutationFn: async ({
      planId,
      billingCycle,
    }: {
      planId: number;
      billingCycle: "monthly" | "annual";
    }) => {
      const result = await portalFetch("/api/portal/settings/billing/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, billing_cycle: billingCycle }),
      });
      return unwrapPortalResult<{
        subscription?: BillingSubscription;
        checkout_url?: string;
        error?: string;
      }>(router, result);
    },
  });

  const changePlanMutation = useMutation({
    mutationFn: async ({
      planId,
      billingCycle,
    }: {
      planId: number;
      billingCycle: "monthly" | "annual";
    }) => {
      const result = await portalFetch("/api/portal/settings/billing/change-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, billing_cycle: billingCycle }),
      });
      return unwrapPortalResult<{ status?: string; error?: string }>(router, result);
    },
  });

  const { data: historyData } = useQuery({
    queryKey: BILLING_HISTORY_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/settings/billing/history");
      return unwrapPortalResult<{ payments: SubscriptionPayment[] }>(router, result);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: async () => {
      const result = await portalFetch("/api/portal/settings/billing/cancel", { method: "POST" });
      return unwrapPortalResult<{ status?: string; error?: string }>(router, result);
    },
  });

  async function startBilling(
    planId: number,
    billingCycle: "monthly" | "annual",
  ): Promise<string | null> {
    try {
      const data = await startMutation.mutateAsync({ planId, billingCycle });
      refetch();
      return data.checkout_url ?? null;
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't start billing", err.message);
      return null;
    }
  }

  async function changePlan(planId: number, billingCycle: "monthly" | "annual"): Promise<boolean> {
    try {
      await changePlanMutation.mutateAsync({ planId, billingCycle });
      toast.success("Plan change scheduled for your next renewal date");
      queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEY });
      return true;
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't change plan", err.message);
      return false;
    }
  }

  // The most recent PAID charge's own card details -- Settings -> Billing's
  // "Payment method" card. Not necessarily historyData[0] (that's newest
  // by created_at regardless of status, and a failed/pending attempt
  // carries no card at all yet).
  const lastPaidCard =
    historyData?.payments.find((p) => p.status === "paid" && p.card_last4) ?? null;

  async function cancelBilling(): Promise<boolean> {
    try {
      await cancelMutation.mutateAsync();
      toast.success("Cancellation requested", "This can take a moment to reflect here.");
      queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEY });
      return true;
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't cancel plan", err.message);
      return false;
    }
  }

  return {
    data: data ?? null,
    error: error && isPortalMutationError(error) ? error.message : null,
    startBilling,
    changePlan,
    cancelBilling,
    starting: startMutation.isPending,
    changingPlan: changePlanMutation.isPending,
    cancelling: cancelMutation.isPending,
    history: historyData?.payments ?? null,
    lastPaidCard,
  };
}
