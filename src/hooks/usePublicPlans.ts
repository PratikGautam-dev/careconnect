import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { API_BASE_URL } from "@/lib/staffAuth";

export type PublicPlan = {
  id: number;
  name: string;
  description: string | null;
  price_monthly: number;
  annual_discount_pct: number;
  capabilities: string[];
  max_users: number | null;
  is_popular: boolean;
};

/** Backs /plans -- public/plans_api.py's GET /api/plans, no auth header,
 * reachable by anyone (never onboarded, logged out, or a logged-in-but-
 * blocked hospital admin arriving via SubscriptionGate's "View Plans"
 * link). Deliberately a plain axios call, not portalFetch/staffFetch --
 * those redirect to /portal/login on 401/unauthenticated, which would
 * wrongly bounce an anonymous visitor just browsing this page. */
export function usePublicPlans() {
  const { data, error } = useQuery({
    queryKey: ["public-plans"],
    retry: false,
    queryFn: async () => {
      const res = await axios.get(`${API_BASE_URL}/api/plans`);
      return res.data as { plans: PublicPlan[]; billing_configured: boolean };
    },
  });

  return {
    plans: data?.plans ?? null,
    billingConfigured: data?.billing_configured ?? false,
    error: error ? (error as Error).message : null,
  };
}
