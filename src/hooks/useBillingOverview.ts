import { useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";

export type BillingRow = {
  bill_type: "appointment" | "pharmacy";
  id: number;
  appointment_id: number | null;
  patient_id: number | null;
  invoice_ref: string;
  patient_name: string;
  patient_phone: string | null;
  doctor_name: string | null;
  prescription_id: number | null;
  amount: number;
  amount_paid: number;
  payment_status: string;
  method: string | null;
  date: string;
  refund_amount: number;
  refund_reason: string | null;
};

export type BillingStats = {
  total_billed: number;
  appointment_bills_total: number;
  appointment_bills_count: number;
  pharmacy_bills_total: number;
  pharmacy_bills_count: number;
  net_collected: number;
  outstanding: number;
  outstanding_count: number;
  refunded: number;
  refund_count: number;
};

export type CollectionByService = { service: string; billed: number; collected: number };
export type PatientClearance = { patient_name: string; appointment_balance: number; pharmacy_balance: number; total_due: number };

export type BillingOverview = {
  stats: BillingStats;
  transactions: BillingRow[];
  collection_by_service: CollectionByService[];
  patient_clearance: PatientClearance[];
};

const QUERY_KEY = ["portal-billing-overview"];

/** The combined "Billing & Payments" page's single read -- GET
 * /api/portal/billing/overview (db/repositories/billing_overview.py).
 * Collecting a payment still goes through each domain's own existing
 * mutation (useCollectCashPayment for an appointment bill,
 * usePharmacyBilling's collectPayment for a pharmacy bill) -- invalidate
 * this query key after either succeeds so the combined ledger refreshes. */
export function useBillingOverview(ready: boolean) {
  const queryClient = useQueryClient();
  const { data, error, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/billing/overview");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return result.data as BillingOverview;
    },
  });

  return {
    overview: data,
    error: error instanceof Error ? error.message : null,
    isLoading,
    invalidate: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  };
}
