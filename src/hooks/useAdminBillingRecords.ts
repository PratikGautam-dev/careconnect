import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { openResolvedInvoice } from "@/lib/openInvoice";
import { toast } from "@/lib/toast";

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
  // Razorpay's own invoice for this charge -- the page may not be stored
  // yet; useAdminBillingInvoice's viewInvoice resolves it on first click.
  razorpay_invoice_id: string | null;
  invoice_short_url: string | null;
  created_at: string;
  paid_at: string | null;
};

export type BillingStats = {
  total_revenue: number;
  invoices_issued: number;
  failed_payments_count: number;
  collections: number;
  total_invoiced: number;
  collections_this_month: number;
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

/** Per-charge invoice actions for the admin billing-records table
 * (admin/subscriptions_api.py): "View" (resolves a missing hosted page
 * once from Razorpay) and "Resend" -- Razorpay re-sends its own invoice
 * email to the email the hospital entered at subscription checkout.
 * Every resend is audited server-side. */
export function useAdminBillingInvoice() {
  const [resendingId, setResendingId] = useState<number | null>(null);

  const resendMutation = useMutation({
    mutationFn: async (paymentId: number) => {
      const result = await adminFetch(`/api/admin/billing-records/${paymentId}/resend-invoice`, {
        method: "POST",
      });
      return unwrapAdminResult<unknown>(result);
    },
  });

  function viewInvoice(record: BillingRecord) {
    if (record.invoice_short_url) {
      window.open(record.invoice_short_url, "_blank", "noopener,noreferrer");
      return;
    }
    void openResolvedInvoice(async () => {
      const result = await adminFetch(`/api/admin/billing-records/${record.id}/invoice`);
      return unwrapAdminResult<{ invoice_url: string | null }>(result).invoice_url;
    });
  }

  async function resendInvoice(paymentId: number) {
    setResendingId(paymentId);
    try {
      await resendMutation.mutateAsync(paymentId);
      toast.success("Invoice email resent");
    } catch (err) {
      toast.error(
        "Couldn't resend invoice",
        err instanceof Error ? err.message : "Something went wrong.",
      );
    } finally {
      setResendingId(null);
    }
  }

  return { resendingId, viewInvoice, resendInvoice };
}
