"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Eye } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import type { AppointmentBillingHospitalRow, AppointmentBillingPaymentRow } from "@/hooks/useAppointmentBilling";

function money(value: number): string {
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const PAYMENT_STATUS_LABEL: Record<AppointmentBillingPaymentRow["status"], string> = {
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
  expired: "Expired",
  pay_at_hospital: "Pay at Hospital",
};
const PAYMENT_STATUS_TONE: Record<AppointmentBillingPaymentRow["status"], "success" | "clay" | "neutral"> = {
  paid: "success",
  pending: "clay",
  failed: "clay",
  expired: "neutral",
  pay_at_hospital: "clay",
};

/** Column defs for the Appointment Billing overview page's "Collections by
 * Hospital" table -- one row per hospital in the selected date range
 * (useAppointmentBillingByHospital). Deliberately wide (reconciliation
 * needs every one of these numbers visible at once, not tucked behind a
 * details toggle) -- the platform/hospital gateway split and the two
 * payable_* columns are the actual "who's holding whose money" answer, the
 * whole point of this page. */
export function createHospitalBillingColumns(): ColumnDef<AppointmentBillingHospitalRow>[] {
  return [
    {
      id: "hospital",
      header: "Hospital",
      cell: ({ row }) => (
        <span className="text-ink-900 font-semibold">{row.original.hospital_name}</span>
      ),
    },
    {
      id: "online",
      header: "Online",
      cell: ({ row }) => <span className="text-ink-600">{money(row.original.online_collected)}</span>,
    },
    {
      id: "cash",
      header: "Cash",
      cell: ({ row }) => <span className="text-ink-600">{money(row.original.cash_collected)}</span>,
    },
    {
      id: "total",
      header: "Total Collected",
      cell: ({ row }) => (
        <span className="text-ink-900 font-semibold">{money(row.original.total_collected)}</span>
      ),
    },
    {
      id: "gatewaySplit",
      header: "Platform / Hospital Gateway",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">
          {money(row.original.platform_gateway_collected)} / {money(row.original.hospital_gateway_collected)}
        </span>
      ),
    },
    {
      id: "platformShare",
      header: "Platform's Share",
      cell: ({ row }) => <span className="text-ink-600">{money(row.original.platform_share)}</span>,
    },
    {
      id: "payableToHospital",
      header: "Payable to Hospital",
      cell: ({ row }) =>
        row.original.payable_to_hospital > 0 ? (
          <span className="text-clay-700 font-semibold">{money(row.original.payable_to_hospital)}</span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      id: "payableToPlatform",
      header: "Payable to Platform",
      cell: ({ row }) =>
        row.original.payable_to_platform > 0 ? (
          <span className="text-brand-700 font-semibold">{money(row.original.payable_to_platform)}</span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      id: "refundsPending",
      header: "Refunds Pending",
      cell: ({ row }) =>
        row.original.refund_pending_count > 0 ? (
          <Badge tone="clay">
            {row.original.refund_pending_count} · {money(row.original.refund_pending_amount)}
          </Badge>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <Link
          href={`/admin/appointment-billing/${row.original.hospital_id}`}
          onClick={(e) => e.stopPropagation()}
          className="text-brand-600 gap-space-1 inline-flex items-center text-[12.5px] font-semibold hover:underline"
        >
          <Eye size={13} /> View
        </Link>
      ),
    },
  ];
}

/** Column defs for the per-tenant detail page's payment-row list
 * (useAppointmentBillingPayments) -- also reusable platform-wide (a
 * "recent payments" strip) since hospital_id is nullable on the underlying
 * type; only shown when present. */
export function createAppointmentPaymentColumns(showHospital: boolean): ColumnDef<AppointmentBillingPaymentRow>[] {
  const columns: ColumnDef<AppointmentBillingPaymentRow>[] = [];
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
          <p className="text-ink-400 text-[11.5px]">{row.original.reference_id || `#${row.original.id}`}</p>
        </div>
      ),
    },
    {
      id: "amount",
      header: "Amount",
      cell: ({ row }) => <span className="text-ink-900 font-semibold">{money(row.original.amount)}</span>,
    },
    {
      id: "method",
      header: "Mode",
      cell: ({ row }) => (
        <Badge tone={row.original.method === "online" ? "brand" : "neutral"}>
          {row.original.method === "online" ? "Online" : "Cash"}
        </Badge>
      ),
    },
    {
      id: "gateway",
      header: "Gateway",
      cell: ({ row }) => (
        <span className="text-ink-600">
          {row.original.gateway_account === "platform" ? "Platform" : "Own Razorpay"}
        </span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge tone={PAYMENT_STATUS_TONE[row.original.status]}>{PAYMENT_STATUS_LABEL[row.original.status]}</Badge>
      ),
    },
    {
      id: "refund",
      header: "Refunded",
      cell: ({ row }) =>
        row.original.refund_amount ? (
          <span className="text-error font-medium">{money(row.original.refund_amount)}</span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      id: "createdAt",
      header: "Date",
      cell: ({ row }) => (
        <span className="text-ink-600 whitespace-nowrap">{formatDateTime(row.original.created_at)}</span>
      ),
    },
  );
  return columns;
}
