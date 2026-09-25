"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

export type BillingRecordRow = {
  id: string;
  invoiceNo: string;
  hospital: string;
  plan: string;
  amount: number;
  paymentMethod: string;
  issueDate: string;
  dueDate: string;
  status: "Paid" | "Failed" | "Pending";
};

const STATUS_TONE: Record<BillingRecordRow["status"], "success" | "clay" | "neutral"> = {
  Paid: "success",
  Failed: "clay",
  Pending: "clay",
};

/** Column defs for the Plans & Billing "Recent Billing Records" table --
 * fully mock, same reasoning as subscriptions/_components/subscription-
 * columns.tsx (no billing/invoice model in the backend yet). */
export function createBillingColumns(): ColumnDef<BillingRecordRow>[] {
  return [
    {
      id: "invoiceNo",
      header: "Invoice #",
      cell: ({ row }) => <span className="text-brand-600 font-semibold">{row.original.invoiceNo}</span>,
    },
    {
      id: "hospital",
      header: "Hospital",
      cell: ({ row }) => <span className="text-ink-900 font-semibold">{row.original.hospital}</span>,
    },
    {
      id: "plan",
      header: "Plan",
      cell: ({ row }) => <span className="text-ink-600">{row.original.plan}</span>,
    },
    {
      id: "amount",
      header: "Amount",
      cell: ({ row }) => (
        <span className="text-ink-900 font-semibold">${row.original.amount.toLocaleString()}.00</span>
      ),
    },
    {
      id: "paymentMethod",
      header: "Payment Method",
      cell: ({ row }) => <span className="text-ink-600">{row.original.paymentMethod}</span>,
    },
    {
      id: "issueDate",
      header: "Issue Date",
      cell: ({ row }) => <span className="text-ink-600 whitespace-nowrap">{row.original.issueDate}</span>,
    },
    {
      id: "dueDate",
      header: "Due Date",
      cell: ({ row }) => <span className="text-ink-600 whitespace-nowrap">{row.original.dueDate}</span>,
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <Badge tone={STATUS_TONE[row.original.status]}>{row.original.status}</Badge>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: () => (
        <button
          type="button"
          onClick={(e) => e.stopPropagation()}
          aria-label="More actions"
          className="text-ink-400 hover:bg-paper flex h-7 w-7 items-center justify-center rounded-md hover:text-ink-700"
        >
          <MoreVertical size={15} />
        </button>
      ),
    },
  ];
}
