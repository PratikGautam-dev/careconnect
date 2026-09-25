"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import {
  TRIAL_DURATION_OPTIONS,
  type BillingCycle,
  type SubscriptionRecord,
} from "@/hooks/useAdminSubscriptions";

type Mode = "trial" | "manual";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  record: SubscriptionRecord;
  plans: { id: number; name: string }[];
  onStartTrial: (hospitalId: number, planId: number, trialDays: number | null) => Promise<boolean>;
  onMarkManuallyBilled: (
    hospitalId: number,
    planId: number,
    billingCycle: BillingCycle,
    note: string,
  ) => Promise<boolean>;
  startingTrial: boolean;
  markingManuallyBilled: boolean;
};

/** Replaces the old one-size-fits-all "pick any status + payment_status +
 * dates" form -- see this feature's own planning discussion: that form let
 * an admin mark payment_status='paid' with no real payment behind it (an
 * accounting-reconciliation risk once real Razorpay billing exists
 * alongside it), and had no clean way to express "15-day trial" or "never
 * expires" without hand-computing a renewal date.
 *
 * Two explicit actions instead, picked via the tab-like toggle below:
 *   - Start Trial: the common path, no payment concept at all.
 *   - Mark as Manually Billed: rare, requires a reference note (audit-
 *     logged, not stored on the row itself), the ONLY manual path that
 *     sets status='active'/payment_status='paid'. */
export function AssignSubscriptionDialog({
  open,
  onOpenChange,
  record,
  plans,
  onStartTrial,
  onMarkManuallyBilled,
  startingTrial,
  markingManuallyBilled,
}: Props) {
  const [mode, setMode] = useState<Mode>("trial");
  const [planId, setPlanId] = useState<string>(
    record.plan_id != null ? String(record.plan_id) : String(plans[0]?.id ?? ""),
  );
  const [trialDays, setTrialDays] = useState<string>("30");
  const [billingCycle, setBillingCycle] = useState<BillingCycle>(record.billing_cycle ?? "monthly");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const saving = startingTrial || markingManuallyBilled;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!planId) {
      setError("Select a plan.");
      return;
    }
    if (mode === "trial") {
      const days = trialDays === "unlimited" ? null : Number(trialDays);
      const ok = await onStartTrial(record.hospital_id, Number(planId), days);
      if (ok) onOpenChange(false);
    } else {
      if (!note.trim()) {
        setError("A payment reference/note is required (e.g. invoice number, transfer date).");
        return;
      }
      const ok = await onMarkManuallyBilled(
        record.hospital_id,
        Number(planId),
        billingCycle,
        note.trim(),
      );
      if (ok) onOpenChange(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>
          {record.status === "unassigned" ? "Assign Plan" : "Edit Subscription"}
        </DialogTitle>
        <p className="text-hint mb-space-4">{record.hospital_name}</p>

        <div className="mb-space-4 flex rounded-md bg-black/4 p-1">
          <button
            type="button"
            onClick={() => setMode("trial")}
            className={cn(
              "py-space-2 flex-1 rounded-md text-[12.5px] font-semibold transition-colors duration-150",
              mode === "trial" ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]" : "text-ink-500",
            )}
          >
            Start Trial
          </button>
          <button
            type="button"
            onClick={() => setMode("manual")}
            className={cn(
              "py-space-2 flex-1 rounded-md text-[12.5px] font-semibold transition-colors duration-150",
              mode === "manual" ? "bg-card text-ink-900 shadow-[var(--shadow-sm)]" : "text-ink-500",
            )}
          >
            Manually Billed
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-space-4">
          {error && <p className="text-error text-[12.5px]">{error}</p>}

          <label className="block text-[12.5px]">
            <span className="text-hint mb-space-1 block">Plan</span>
            <select
              value={planId}
              onChange={(e) => setPlanId(e.target.value)}
              className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          {mode === "trial" ? (
            <label className="block text-[12.5px]">
              <span className="text-hint mb-space-1 block">Trial Length</span>
              <select
                value={trialDays}
                onChange={(e) => setTrialDays(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
              >
                {TRIAL_DURATION_OPTIONS.map((opt) => (
                  <option key={opt.label} value={opt.value ?? "unlimited"}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <span className="text-ink-400 mt-space-1 block text-[11.5px]">
                No payment is involved during a trial -- nothing to mark paid/pending.
              </span>
            </label>
          ) : (
            <>
              <label className="block text-[12.5px]">
                <span className="text-hint mb-space-1 block">Billing Cycle</span>
                <select
                  value={billingCycle}
                  onChange={(e) => setBillingCycle(e.target.value as BillingCycle)}
                  className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
                >
                  <option value="monthly">Monthly</option>
                  <option value="annual">Annual</option>
                </select>
              </label>
              <label className="block text-[12.5px]">
                <span className="text-hint mb-space-1 block">
                  Payment Reference / Note (required)
                </span>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="e.g. Invoice #1204, paid via NEFT on 20 Sep 2026"
                  className="border-line bg-card px-space-3 py-space-2 text-ink-900 w-full rounded-md border text-[13px]"
                />
                <span className="text-ink-400 mt-space-1 block text-[11.5px]">
                  Logged to the audit trail -- use this only for payment received outside Razorpay
                  (e.g. wire transfer/invoice).
                </span>
              </label>
            </>
          )}

          <div className="gap-space-2 flex justify-end">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="border-line text-ink-700 px-space-4 hover:bg-paper h-9 rounded-md border text-[13px] font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="bg-brand-600 hover:bg-brand-700 px-space-4 h-9 rounded-md text-[13px] font-semibold text-white transition-colors duration-150 disabled:opacity-60"
            >
              {saving ? "Saving…" : mode === "trial" ? "Start Trial" : "Mark as Billed"}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
