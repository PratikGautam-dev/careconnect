"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { RotateCw } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatShortDateTime } from "@/lib/formatDate";
import type { RefundRequest, RefundStatus } from "@/hooks/useRefunds";

export const REFUND_STATUS_LABELS: Record<RefundStatus, string> = {
  pending_approval: "Pending Approval",
  approved: "Approved",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  rejected: "Rejected",
};

export const REFUND_STATUS_TONES: Record<RefundStatus, "success" | "clay" | "neutral" | "brand"> = {
  pending_approval: "clay",
  approved: "brand",
  processing: "brand",
  completed: "success",
  failed: "neutral",
  rejected: "neutral",
};

type CreateRefundColumnsOptions = {
  /** Gates both the select column and the approve/reject/check-status
   * actions -- a viewer with read-only billing access sees the queue but
   * can't act on it. */
  canWrite: boolean;
  selected: Set<number>;
  toggleSelected: (id: number, checked: boolean) => void;
  toggleSelectAll: (checked: boolean) => void;
  allSelected: boolean;
  selectableCount: number;
  approvingId: number | null;
  rejectingId: number | null;
  syncingId: number | null;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
  onSync: (id: number) => void;
};

/** Column defs for the Billing -> Refunds approval queue -- only
 * pending_approval/processing rows get action buttons (a completed/
 * rejected/failed row is a read-only record at that point). */
export function createRefundColumns({
  canWrite,
  selected,
  toggleSelected,
  toggleSelectAll,
  allSelected,
  selectableCount,
  approvingId,
  rejectingId,
  syncingId,
  onApprove,
  onReject,
  onSync,
}: CreateRefundColumnsOptions): ColumnDef<RefundRequest>[] {
  const selectColumn: ColumnDef<RefundRequest>[] = canWrite
    ? [
        {
          id: "select",
          enableHiding: false,
          header: () => (
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(e) => toggleSelectAll(e.target.checked)}
              disabled={selectableCount === 0}
              className="accent-brand-600 h-4 w-4"
              aria-label="Select all pending refunds"
            />
          ),
          cell: ({ row }) => {
            const r = row.original;
            if (r.status !== "pending_approval") return null;
            return (
              <input
                type="checkbox"
                checked={selected.has(r.id)}
                onChange={(e) => toggleSelected(r.id, e.target.checked)}
                className="accent-brand-600 h-4 w-4"
                aria-label={`Select refund #${r.id}`}
              />
            );
          },
        },
      ]
    : [];

  const dataColumns: ColumnDef<RefundRequest>[] = [
    {
      id: "patient",
      header: "Patient",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div>
            <span className="text-ink-900 truncate font-semibold">{r.patient_name || "—"}</span>
            {r.patient_phone && (
              <span className="text-ink-400 block text-[11.5px]">{r.patient_phone}</span>
            )}
          </div>
        );
      },
    },
    {
      id: "appointment",
      header: "Appointment",
      cell: ({ row }) => (
        <span className="text-ink-600">
          {row.original.appointment_scheduled_at
            ? formatShortDateTime(row.original.appointment_scheduled_at)
            : "—"}
        </span>
      ),
    },
    {
      id: "cancelled_by",
      header: "Cancelled by",
      cell: ({ row }) => (
        <span className="text-ink-600 capitalize">{row.original.cancelled_by}</span>
      ),
    },
    {
      id: "amount",
      header: "Refund amount",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div>
            <span className="text-ink-900 font-semibold">
              ₹{r.refund_amount.toLocaleString("en-IN")}
            </span>
            {r.deduction_amount > 0 && (
              <span className="text-ink-400 block text-[11px]">
                ₹{r.deduction_amount.toLocaleString("en-IN")} deducted ({r.deduction_percent}%)
              </span>
            )}
          </div>
        );
      },
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div className="gap-space-1 flex flex-col items-start">
            <Badge tone={REFUND_STATUS_TONES[r.status]}>{REFUND_STATUS_LABELS[r.status]}</Badge>
            {r.status === "failed" && r.failure_reason && (
              <span className="text-error text-[11px]">{r.failure_reason}</span>
            )}
          </div>
        );
      },
    },
  ];

  const actionsColumn: ColumnDef<RefundRequest>[] = canWrite
    ? [
        {
          id: "actions",
          header: "",
          cell: ({ row }) => {
            const r = row.original;
            if (r.status === "pending_approval") {
              return (
                <div className="gap-space-2 flex">
                  <Button size="md" onClick={() => onApprove(r.id)} disabled={approvingId === r.id}>
                    {approvingId === r.id ? "Approving…" : "Approve"}
                  </Button>
                  <Button
                    size="md"
                    variant="secondary"
                    onClick={() => onReject(r.id)}
                    disabled={rejectingId === r.id}
                  >
                    {rejectingId === r.id ? "Rejecting…" : "Reject"}
                  </Button>
                </div>
              );
            }
            if (r.status === "processing" || r.status === "failed") {
              return (
                <Button
                  size="md"
                  variant="secondary"
                  onClick={() => onSync(r.id)}
                  disabled={syncingId === r.id}
                >
                  <RotateCw size={13} /> {syncingId === r.id ? "Checking…" : "Check status"}
                </Button>
              );
            }
            return null;
          },
        },
      ]
    : [];

  return [...selectColumn, ...dataColumns, ...actionsColumn];
}
