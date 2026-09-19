"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { useHolidayApplication } from "@/hooks/useHolidayApplication";
import { useLeavePolicy } from "@/hooks/useLeavePolicy";
import type { LeaveType } from "@/hooks/useLeaveRequests";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

const REASON_MAX = 500;

function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Fired the moment the request is created (and, for an admin, auto-
   * approved server-side) -- lets the caller's own review-queue list
   * refresh; the dialog closes itself on success. */
  onCreated?: () => void;
  /** When set, this submits leave ON BEHALF OF that staff/doctor identity
   * (POST .../leave-requests/staff/{id}, "Manage leave" quick action on
   * the Staff/Doctor detail panels) instead of the caller's own leave
   * (POST .../leave-requests/mine, the Leave Requests page's own top-right
   * button). Both are auto-approved server-side, so the form/UX is
   * identical either way -- only the submit target and title change. */
  subjectStaffId?: number;
  subjectName?: string;
};

/** Leave-submit modal shared by two quick-create entry points: the admin
 * Leave Requests page's own top-right button (submits the caller's own
 * leave, subjectStaffId unset) and the Staff/Doctor detail panels' "Manage
 * leave" quick action (submits on behalf of that staff/doctor,
 * subjectStaffId set). Both land in the same leave_requests table and are
 * auto-approved immediately server-side -- an admin submitting their own
 * doesn't need to wait on their own review, and an admin submitting FOR
 * someone else already had to hold "leave_requests" write to reach that
 * endpoint at all, so there's nothing left to review either way.
 *
 * leave_types itself is read via useLeavePolicy (GET .../policy, gated by
 * "leave_requests" view -- the SAME permission that already gates both the
 * Leave Requests page and the "Manage leave" quick action, so nothing extra
 * is needed for this dialog to work), not via useHolidayApplication's own
 * GET .../mine -- that one is gated by "holiday_application" view instead,
 * which is a completely separate permission (the Holiday Application
 * page's own), confirmed with the user NOT to couple this dialog to:
 * turning that on for Admin (who doesn't need the Holiday Application page
 * at all, this button already covers the same need) would also make that
 * nav item appear for them. */
export function NewLeaveRequestDialog({
  open,
  onOpenChange,
  onCreated,
  subjectStaffId,
  subjectName,
}: Props) {
  const { leaveTypes } = useLeavePolicy(open);
  // canView=false -- this dialog only submits, it doesn't need Holiday
  // Application's own history/balance/leave_types GET at all. Its submit()
  // always posts to .../mine, so it's only used in the "own leave" mode
  // below -- the "on behalf of" mode posts directly via staffFetch instead.
  const { submitting: submittingOwn, submit: submitOwn } = useHolidayApplication(false);
  const [submittingForOther, setSubmittingForOther] = useState(false);
  const submitting = subjectStaffId != null ? submittingForOther : submittingOwn;

  async function submitForOther(
    staffId: number,
    input: { leave_type: string; from_date: string; to_date: string; is_half_day: boolean; reason: string },
  ): Promise<string | null> {
    setSubmittingForOther(true);
    const result = await staffFetch(`/api/portal/leave-requests/staff/${staffId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    setSubmittingForOther(false);
    if (!result.ok) return result.unauthorized ? "Session expired -- please log in again." : result.error;
    toast.success("Leave request created");
    return null;
  }

  const [leaveType, setLeaveType] = useState<LeaveType>("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [duration, setDuration] = useState<"full" | "half">("full");
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // leaveTypes only arrives after the dialog's own /mine fetch resolves --
  // a derived fallback rather than syncing it into state via an effect;
  // once the caller picks something explicitly, that choice wins.
  const selectedLeaveType = leaveType || leaveTypes[0] || "";

  function resetForm() {
    setLeaveType("");
    setFromDate("");
    setToDate("");
    setDuration("full");
    setReason("");
    setFormError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!selectedLeaveType) {
      setFormError("Please select a leave type.");
      return;
    }
    if (!fromDate || !toDate) {
      setFormError("Both From date and To date are required.");
      return;
    }
    if (toDate < fromDate) {
      setFormError("To date can't be before From date.");
      return;
    }
    if (duration === "half" && toDate !== fromDate) {
      setFormError("Half day only applies to a single date -- set To date the same as From date.");
      return;
    }
    if (!reason.trim()) {
      setFormError("Please enter a reason for leave.");
      return;
    }

    const input = {
      leave_type: selectedLeaveType,
      from_date: fromDate,
      to_date: toDate,
      is_half_day: duration === "half",
      reason: reason.trim(),
    };
    const err = subjectStaffId != null ? await submitForOther(subjectStaffId, input) : await submitOwn(input);
    if (err) {
      setFormError(err);
      return;
    }
    resetForm();
    onOpenChange(false);
    onCreated?.();
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) resetForm();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogTitle>{subjectStaffId != null ? `New leave request${subjectName ? ` for ${subjectName}` : ""}` : "New leave request"}</DialogTitle>
        <DialogDescription>
          {subjectStaffId != null
            ? "This is approved automatically -- it skips the review queue."
            : "Submitting your own leave here is approved automatically -- it skips the review queue."}
        </DialogDescription>
        <form onSubmit={handleSubmit} className="gap-space-3 grid grid-cols-1">
          <Field label="Leave type" htmlFor="new_leave_type" required>
            <select
              id="new_leave_type"
              value={selectedLeaveType}
              onChange={(e) => setLeaveType(e.target.value as LeaveType)}
              disabled={leaveTypes.length === 0}
              className="border-line bg-card px-space-3 text-ink-900 disabled:bg-paper disabled:text-ink-400 h-11 w-full rounded-md border text-[14px] disabled:cursor-not-allowed"
            >
              {leaveTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>

          <div className="gap-x-space-4 grid grid-cols-1 sm:grid-cols-2">
            <Field label="From date" htmlFor="new_from_date" required>
              <Input
                id="new_from_date"
                type="date"
                value={fromDate}
                min={todayKey()}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </Field>
            <Field label="To date" htmlFor="new_to_date" required>
              <Input
                id="new_to_date"
                type="date"
                value={toDate}
                min={fromDate || todayKey()}
                onChange={(e) => setToDate(e.target.value)}
              />
            </Field>
          </div>

          <Field label="Leave duration" required>
            <div className="gap-space-4 flex items-center">
              {(["full", "half"] as const).map((d) => (
                <label key={d} className="gap-space-2 text-ink-700 flex items-center text-[13.5px]">
                  <input
                    type="radio"
                    name="new_leave_duration"
                    checked={duration === d}
                    onChange={() => setDuration(d)}
                    className="accent-brand-600 h-4 w-4"
                  />
                  {d === "full" ? "Full day" : "Half day"}
                </label>
              ))}
            </div>
          </Field>

          <Field
            label="Reason for leave"
            htmlFor="new_reason"
            required
            hint={`${reason.length}/${REASON_MAX}`}
          >
            <Textarea
              id="new_reason"
              rows={3}
              maxLength={REASON_MAX}
              placeholder="Enter reason for leave..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>

          {formError && <p className="text-error text-[12.5px] font-medium">{formError}</p>}

          <div>
            <Button type="submit" disabled={submitting}>
              <Send size={14} /> {submitting ? "Submitting…" : "Submit request"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
