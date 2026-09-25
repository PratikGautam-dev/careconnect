import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { toast } from "@/lib/toast";

export type SubscriptionStatus =
  | "unassigned"
  | "trial"
  | "authorization_pending"
  | "active"
  | "renewal_due"
  | "expired"
  | "cancelled";
export type BillingCycle = "monthly" | "annual";
export type PaymentStatus = "paid" | "pending" | "failed";

export type SubscriptionRecord = {
  hospital_id: number;
  hospital_name: string;
  plan_id: number | null;
  plan_name: string | null;
  billing_cycle: BillingCycle | null;
  status: SubscriptionStatus;
  payment_status: PaymentStatus | null;
  start_date: string | null;
  renewal_date: string | null;
  // Real, live-computed from active doctors+staff (db/repositories/
  // dashboard.get_staffing_stats()) -- never a stored/stale number.
  seats_used: number;
  max_users: number | null;
  // Monthly-equivalent price for this hospital's plan/cycle -- null when
  // unassigned.
  monthly_value: number | null;
  // Set once the hospital has set up real Razorpay billing themselves
  // (Settings -> Billing, portal/routes/billing_subscription.py) --
  // status/payment_status become webhook-owned from then on, so this
  // page's manual assign/edit form must not touch a row with this set
  // (the backend also refuses it with a 409; the UI hides the option so
  // an operator isn't offered a button that will just error).
  razorpay_subscription_id: string | null;
};

export type SubscriptionAssignPayload = {
  plan_id: number;
  billing_cycle: BillingCycle;
  status: SubscriptionStatus;
  payment_status: PaymentStatus;
  start_date?: string;
  renewal_date?: string;
};

// Presets a trial can be started for -- must match db/repositories/
// subscriptions.py's TRIAL_DURATION_PRESETS exactly; `null` means
// unlimited (never expires).
export const TRIAL_DURATION_OPTIONS: { value: number | null; label: string }[] = [
  { value: 7, label: "7 days" },
  { value: 15, label: "15 days" },
  { value: 30, label: "30 days" },
  { value: 60, label: "60 days" },
  { value: 90, label: "90 days" },
  { value: null, label: "No expiry (unlimited)" },
];

const SUBSCRIPTIONS_QUERY_KEY = ["admin-subscriptions"] as const;

/** Real hospital<->plan assignment (admin/subscriptions_api.py) -- backs
 * /admin/subscriptions. Every hospital appears here, `status: "unassigned"`
 * until a super admin assigns it a plan; `seats_used` is always the real
 * active doctor+staff count, not a placeholder. */
export function useAdminSubscriptions() {
  const queryClient = useQueryClient();

  const { data, error, refetch } = useQuery({
    queryKey: SUBSCRIPTIONS_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/subscriptions");
      return unwrapAdminResult<{
        subscriptions: SubscriptionRecord[];
        plans: { id: number; name: string }[];
      }>(result);
    },
  });

  const assignMutation = useMutation({
    mutationFn: async ({
      hospitalId,
      payload,
    }: {
      hospitalId: number;
      payload: SubscriptionAssignPayload;
    }) => {
      const result = await adminFetch(`/api/admin/subscriptions/${hospitalId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<{ subscription?: unknown; errors?: string[] }>(result);
    },
  });

  const unassignMutation = useMutation({
    mutationFn: async (hospitalId: number) => {
      const result = await adminFetch(`/api/admin/subscriptions/${hospitalId}`, {
        method: "DELETE",
      });
      return unwrapAdminResult<{ status?: string }>(result);
    },
  });

  const cancelBillingMutation = useMutation({
    mutationFn: async (hospitalId: number) => {
      const result = await adminFetch(`/api/admin/subscriptions/${hospitalId}/cancel-billing`, {
        method: "POST",
      });
      return unwrapAdminResult<{ status?: string; error?: string }>(result);
    },
  });

  const startTrialMutation = useMutation({
    mutationFn: async ({
      hospitalId,
      planId,
      trialDays,
    }: {
      hospitalId: number;
      planId: number;
      trialDays: number | null;
    }) => {
      const result = await adminFetch(`/api/admin/subscriptions/${hospitalId}/start-trial`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, trial_days: trialDays }),
      });
      return unwrapAdminResult<{ subscription?: unknown; errors?: string[]; error?: string }>(
        result,
      );
    },
  });

  const markManuallyBilledMutation = useMutation({
    mutationFn: async ({
      hospitalId,
      planId,
      billingCycle,
      note,
    }: {
      hospitalId: number;
      planId: number;
      billingCycle: BillingCycle;
      note: string;
    }) => {
      const result = await adminFetch(
        `/api/admin/subscriptions/${hospitalId}/mark-manually-billed`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan_id: planId, billing_cycle: billingCycle, note }),
        },
      );
      return unwrapAdminResult<{ subscription?: unknown; errors?: string[]; error?: string }>(
        result,
      );
    },
  });

  async function assign(hospitalId: number, payload: SubscriptionAssignPayload): Promise<boolean> {
    try {
      const data = await assignMutation.mutateAsync({ hospitalId, payload });
      if (data.errors?.length) {
        toast.error("Couldn't save subscription", data.errors[0]);
        return false;
      }
      toast.success("Subscription saved");
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't save subscription",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  async function unassign(hospitalId: number, hospitalName: string): Promise<boolean> {
    try {
      await unassignMutation.mutateAsync(hospitalId);
      toast.success(`${hospitalName} unassigned from its plan`);
      queryClient.setQueryData(
        SUBSCRIPTIONS_QUERY_KEY,
        (
          prev:
            | { subscriptions: SubscriptionRecord[]; plans: { id: number; name: string }[] }
            | undefined,
        ) =>
          prev
            ? {
                ...prev,
                subscriptions: prev.subscriptions.map((s) =>
                  s.hospital_id === hospitalId
                    ? {
                        ...s,
                        plan_id: null,
                        plan_name: null,
                        billing_cycle: null,
                        status: "unassigned" as const,
                        payment_status: null,
                        start_date: null,
                        renewal_date: null,
                        monthly_value: null,
                        max_users: null,
                      }
                    : s,
                ),
              }
            : prev,
      );
      return true;
    } catch (err) {
      toast.error(
        "Couldn't unassign subscription",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  async function startTrial(
    hospitalId: number,
    planId: number,
    trialDays: number | null,
  ): Promise<boolean> {
    try {
      const data = await startTrialMutation.mutateAsync({ hospitalId, planId, trialDays });
      if (data.errors?.length) {
        toast.error("Couldn't start trial", data.errors[0]);
        return false;
      }
      toast.success("Trial started");
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't start trial",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  async function markManuallyBilled(
    hospitalId: number,
    planId: number,
    billingCycle: BillingCycle,
    note: string,
  ): Promise<boolean> {
    try {
      const data = await markManuallyBilledMutation.mutateAsync({
        hospitalId,
        planId,
        billingCycle,
        note,
      });
      if (data.errors?.length) {
        toast.error("Couldn't mark as manually billed", data.errors[0]);
        return false;
      }
      toast.success("Marked as manually billed");
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't mark as manually billed",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  async function cancelBilling(hospitalId: number, hospitalName: string): Promise<boolean> {
    try {
      await cancelBillingMutation.mutateAsync(hospitalId);
      // Not optimistic -- status flips once the subscription.cancelled
      // webhook actually confirms it (same "webhook owns real-billing
      // state" rule the backend follows), so just tell the operator the
      // request went through rather than guessing the new state here.
      toast.success(`Cancellation requested for ${hospitalName}`);
      return true;
    } catch (err) {
      toast.error(
        "Couldn't cancel billing",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  return {
    subscriptions: data?.subscriptions ?? null,
    plans: data?.plans ?? [],
    error: error ? (error as Error).message : null,
    assign,
    unassign,
    cancelBilling,
    startTrial,
    markManuallyBilled,
    assigning: assignMutation.isPending,
    unassigning: unassignMutation.isPending,
    cancellingBilling: cancelBillingMutation.isPending,
    startingTrial: startTrialMutation.isPending,
    markingManuallyBilled: markManuallyBilledMutation.isPending,
  };
}
