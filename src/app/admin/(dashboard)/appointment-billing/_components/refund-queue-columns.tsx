"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Badge } from "@/components/ui/Badge";
import type { AppointmentBillingRefundRow } from "@/hooks/useAppointmentBilling";

function money(value: number): string {
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// Same statuses/wording db/repositories/refunds.py's STATUS_* constants
// use -- this is a read-only view of the same queue the hospital's own
// portal actions (portal/routes/refunds.py), not a separate vocabulary.
export const REFUND_STATUS_LABEL: Record<AppointmentBillingRefundRow["status"], string> = {
  pending_approval: "Pending Approval",
  approved: "Approved",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  rejected: "Rejected",
};
export const REFUND_STATUS_TONE: Record<
  AppointmentBillingRefundRow["status"],
  "success" | "clay" | "neutral" | "brand"
> = {
  pending_approval: "clay",
  approved: "brand",
  processing: "brand",
  completed: "success",
  failed: "neutral",
  rejected: "neutral",
};

/** Column defs for the Appointment Billing page's "Refund Queue" section --
 * read-only visibility only (confirmed with the user); approve/reject
 * stays in the hospital's own portal. showHospital=false on the per-tenant
 * detail page (redundant there). */
export function createRefundQueueColumns(showHospital: boolean): ColumnDef<AppointmentBillingRefundRow>[] {
  const columns: ColumnDef<AppointmentBillingRefundRow>[] = [];
  if (showHospital) {
    columns.push({
      id: "hospital",
      header: "Hospital",
      cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.hospital_name}</span>,
    });
  }
  columns.push(
    {
      id: "patient",
      header: "Patient",
      cell: ({ row }) => (
        <div>
          <p className="text-ink-900 font-medium">{row.original.patient_name || "—"}</p>
          <p className="text-ink-400 text-[11.5px]">{row.original.patient_phone || "—"}</p>
        </div>
      ),
    },
    {
      id: "appointment",
      header: "Appointment",
      cell: ({ row }) => (
        <span className="text-ink-600">{row.original.reference_id || `#${row.original.appointment_id}`}</span>
      ),
    },
    {
      id: "amount",
      header: "Refund Amount",
      cell: ({ row }) => <span className="text-ink-900 font-semibold">{money(row.original.refund_amount)}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={REFUND_STATUS_TONE[row.original.status]}>{REFUND_STATUS_LABEL[row.original.status]}</Badge>
      ),
    },
    {
      id: "requestedAt",
      header: "Requested",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">{formatDateTime(row.original.created_at)}</span>
      ),
    },
  );
  return columns;
}
