"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { staffFetch } from "@/lib/staffAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { openResolvedInvoice } from "@/lib/openInvoice";
import { toast } from "@/lib/toast";

type InvoiceResponse = {
  razorpay_invoice_id: string | null;
  invoice_url: string | null;
  invoice_status: string | null;
};

/** Billing page's per-payment invoice actions (portal/routes/payments.py):
 * "View invoice" for a row whose hosted page isn't stored yet (resolved
 * once from Razorpay, then saved server-side), and "Send to patient" --
 * WhatsApp only, a tappable "View Invoice" button to the number the
 * booking was made on. Same self-contained shape as
 * useSendAppointmentReminder (owns its own mutation + per-row loading
 * state). */
export function usePaymentInvoice() {
  const router = useRouter();
  const [sendingInvoiceId, setSendingInvoiceId] = useState<number | null>(null);

  const sendMutation = useMutation({
    mutationFn: async (paymentId: number) => {
      const result = await staffFetch(`/api/portal/payments/${paymentId}/send-invoice`, {
        method: "POST",
      });
      return unwrapPortalResult<unknown>(router, result);
    },
  });

  function viewInvoice(paymentId: number) {
    return openResolvedInvoice(async () => {
      const result = await staffFetch(`/api/portal/payments/${paymentId}/invoice`);
      return unwrapPortalResult<InvoiceResponse>(router, result).invoice_url;
    });
  }

  async function sendInvoice(paymentId: number) {
    setSendingInvoiceId(paymentId);
    try {
      await sendMutation.mutateAsync(paymentId);
      toast.success("Invoice sent on WhatsApp");
    } catch (err) {
      if (isPortalMutationError(err)) toast.error("Couldn't send invoice", err.message);
    } finally {
      setSendingInvoiceId(null);
    }
  }

  return { sendingInvoiceId, viewInvoice, sendInvoice };
}
