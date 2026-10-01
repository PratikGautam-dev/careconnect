"use client";

import { Ban, MoreHorizontal, Pencil, TimerReset, XCircle } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { SubscriptionRecord } from "@/hooks/useAdminSubscriptions";

// Mirrors admin/subscriptions_api.py's _NON_TERMINAL_STATUSES exactly --
// razorpay_subscription_id stays set on a row forever as history even
// after the real subscription is cancelled (webhook/razorpay_subscription_
// routes.py never clears it), so "is there a live billed subscription to
// cancel" is id-set AND status still non-terminal, not id-set alone.
const LIVE_BILLING_STATUSES = new Set(["authorization_pending", "active", "renewal_due"]);

type Props = {
  row: SubscriptionRecord;
  onEdit: (row: SubscriptionRecord) => void;
  onExtendTrial: (row: SubscriptionRecord) => void;
  onCancelSubscription: (row: SubscriptionRecord) => void;
  onUnassign: (row: SubscriptionRecord) => void;
  onCancelBilling: (row: SubscriptionRecord) => void;
};

/** Row-level "..." actions menu -- replaces the old split "check a row's
 * box, then find the matching action in a separate Quick Actions panel"
 * flow (confusing: nothing on the row itself showed which action applied
 * to it). Every per-hospital action short of Send Renewal Reminder/
 * Download Invoice (both still placeholders with no real backend, left in
 * the Quick Actions panel) now lives here, scoped to the one row it's
 * opened from, same mutations (assign/unassign/cancelBilling) as before. */
export function SubscriptionCellAction({
  row,
  onEdit,
  onExtendTrial,
  onCancelSubscription,
  onUnassign,
  onCancelBilling,
}: Props) {
  // Real Razorpay billing owns status/payment_status while live (this
  // hospital set it up themselves via Settings -> Billing) -- the manual
  // assign/edit form would just get a 409 from the backend, so nothing
  // else is offered here; Cancel Billing is the only action. Once
  // cancelled/expired, the backend allows manual edits again (the id
  // sticks around as history, not a live-billing marker).
  const isLiveBilled = !!row.razorpay_subscription_id && LIVE_BILLING_STATUSES.has(row.status);

  return (
    <div onClick={(e) => e.stopPropagation()}>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="text-ink-600 hover:text-ink-900 inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-black/4"
          aria-label={`Actions for ${row.hospital_name}`}
        >
          <MoreHorizontal size={16} />
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuGroup>
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            {isLiveBilled ? (
              <DropdownMenuItem variant="destructive" onClick={() => onCancelBilling(row)}>
                <Ban size={14} /> Cancel Billing
              </DropdownMenuItem>
            ) : (
              <>
                <DropdownMenuItem onClick={() => onEdit(row)}>
                  <Pencil size={14} /> {row.status === "unassigned" ? "Assign" : "Upgrade Plan"}
                </DropdownMenuItem>
                {row.status === "trial" && (
                  <DropdownMenuItem onClick={() => onExtendTrial(row)}>
                    <TimerReset size={14} /> Extend Trial
                  </DropdownMenuItem>
                )}
                {row.status !== "unassigned" && row.status !== "cancelled" && (
                  <DropdownMenuItem onClick={() => onCancelSubscription(row)}>
                    <XCircle size={14} /> Cancel Subscription
                  </DropdownMenuItem>
                )}
                {row.status !== "unassigned" && (
                  <DropdownMenuItem variant="destructive" onClick={() => onUnassign(row)}>
                    <Ban size={14} /> Unassign
                  </DropdownMenuItem>
                )}
              </>
            )}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
