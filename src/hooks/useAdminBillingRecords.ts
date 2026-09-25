import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

export type BillingRecord = {
  id: number;
  hospital_id: number;
  hospital_name: string;
  plan_name: string | null;
  billing_cycle: "monthly" | "annual" | null;
  amount: number;
  currency: string;
  status: "paid" | "pending" | "failed";
  razorpay_payment_id: string | null;
  created_at: string;
  paid_at: string | null;
};

export type BillingStats = {
  total_revenue: number;
  invoices_issued: number;
  failed_payments_count: number;
  collections: number;
  total_invoiced: number;
  pending_payments: number;
  failed_payments_amount: number;
};

/** Real "Recent Billing Records" + stat tiles for /admin/plans-billing --
 * backed by admin/subscriptions_api.py's list_billing_records, sourced
 * directly from the payments ledger (payment_for='subscription'), no mock
 * data. Empty until at least one hospital has actually started real
 * billing (Settings -> Billing, portal-side). */
export function useAdminBillingRecords() {
  const { data, error } = useQuery({
    queryKey: ["admin-billing-records"],
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/billing-records");
      return unwrapAdminResult<{ records: BillingRecord[]; stats: BillingStats }>(result);
    },
  });

  return {
    records: data?.records ?? null,
    stats: data?.stats ?? null,
    error: error ? (error as Error).message : null,
  };
}
