"use client";

import { Send, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { RefundPreview } from "@/hooks/useAppointments";

/** The inline "cancel this appointment" row-detail panel, shared by the
 * Doctor appointments and Diagnostic & Lab appointments pages (previously
 * duplicated between them) -- extended with a refund preview computed
 * against db.CANCELLED_BY_HOSPITAL (a staff-portal cancel always refunds
 * the full base fee, no deduction ladder). The preview never blocks
 * cancelling -- it's shown once it resolves, or not at all if it's still
 * loading or the appointment was never paid online. */
export function CancelPanel({
  phone,
  cancelMessage,
  onCancelMessageChange,
  cancelling,
  refundPreview,
  refundPreviewLoading,
  onConfirm,
  onDismiss,
}: {
  phone: string;
  cancelMessage: string;
  onCancelMessageChange: (value: string) => void;
  cancelling: boolean;
  refundPreview: RefundPreview | null;
  refundPreviewLoading: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="border-line bg-paper p-space-3 rounded-lg border">
      <label
        htmlFor={`cancel-msg-${phone}`}
        className="mb-space-2 text-ink-600 block text-[12px] font-semibold"
      >
        Message to send {phone} on WhatsApp
      </label>
      <textarea
        id={`cancel-msg-${phone}`}
        value={cancelMessage}
        onChange={(e) => onCancelMessageChange(e.target.value)}
        rows={2}
        className="mb-space-2 border-line bg-card px-space-3 py-space-2 text-ink-900 focus:border-brand-400 h-16 w-full resize-none rounded-md border text-[13px] outline-none"
      />

      {refundPreviewLoading && (
        <p className="mb-space-2 text-ink-400 text-[12px]">Checking refund amount…</p>
      )}
      {!refundPreviewLoading && refundPreview?.refundable && (
        <p className="mb-space-2 text-success bg-success-tint px-space-3 py-space-2 rounded-md text-[12.5px] font-medium">
          A refund of ₹{refundPreview.refund_amount?.toLocaleString("en-IN")} will be issued (full
          fee -- GST/platform fee of ₹
          {(
            (refundPreview.gst_amount ?? 0) + (refundPreview.platform_fee_amount ?? 0)
          ).toLocaleString("en-IN")}{" "}
          is not refundable).
        </p>
      )}
      {!refundPreviewLoading &&
        refundPreview &&
        !refundPreview.refundable &&
        refundPreview.base_amount != null && (
          <p className="mb-space-2 text-ink-400 text-[12px]">
            No refund due -- already refunded in full for this appointment.
          </p>
        )}

      <div className="gap-space-2 flex">
        <Button
          size="md"
          onClick={onConfirm}
          disabled={cancelling}
          className="bg-error hover:bg-error/90 active:bg-error/80"
        >
          <Send size={13} /> {cancelling ? "Cancelling…" : "Send & cancel"}
        </Button>
        <Button size="md" variant="secondary" onClick={onDismiss} disabled={cancelling}>
          <X size={13} /> Dismiss
        </Button>
      </div>
    </div>
  );
}
