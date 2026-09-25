import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";

// Matches portal/routes/payments.py's list_payments() -> db/repositories/
// payments.py's list_payments_for_hospital(): one row per payment ATTEMPT
// (a retry appends a new row -- see that table's own comment), joined with
// its appointment's already-denormalized patient_name/phone/reference_id
// (no separate patients table join needed) and doctor name.
export type PaymentRow = {
  id: number;
  appointment_id: number;
  attempt_no: number;
  amount: number;
  currency: string;
  method: "online" | "pay_at_hospital";
  status: "pending" | "paid" | "failed" | "expired" | "pay_at_hospital";
  razorpay_order_id: string | null;
  razorpay_payment_id: string | null;
  bank_reference: string | null;
  created_at: string;
  updated_at: string | null;
  paid_at: string | null;
  patient_name: string | null;
  patient_phone: string | null;
  reference_id: string | null;
  appointment_scheduled_at: string | null;
  doctor_name: string | null;
};

export const PAYMENTS_QUERY_KEY = ["portal-payments"] as const;

/** Read-only: the /portal/billing transaction ledger -- GET /api/portal/payments. */
export function usePayments(canView: boolean) {
  const router = useRouter();

  const {
    data,
    error: queryError,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: PAYMENTS_QUERY_KEY,
    enabled: canView,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/payments");
      return unwrapPortalResult<PaymentRow[]>(router, result);
    },
  });

  return {
    payments: data ?? null,
    error: queryError ? "Couldn't load payments — try again." : null,
    isFetching,
    load: refetch,
  };
}
