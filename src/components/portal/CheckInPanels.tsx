"use client";

import { useState, useSyncExternalStore } from "react";
import { AlertTriangle, Clock, MapPin, Smartphone, XCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Textarea } from "@/components/ui/Input";
import type { CheckInProblem } from "@/hooks/useCheckInActions";
import type { CheckInRequest } from "@/hooks/usePortalAttendanceToday";
import { formatTimeOnly } from "@/lib/formatDate";

function subscribeToPointerChange(onChange: () => void) {
  const query = window.matchMedia("(pointer: coarse)");
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** True on a phone/tablet (touch screen), false on a laptop/desktop. */
function useIsTouchDevice(): boolean {
  return useSyncExternalStore(
    subscribeToPointerChange,
    () => window.matchMedia("(pointer: coarse)").matches,
    () => true,
  );
}

/** The "use your phone" nudge shown above the check-in buttons. Phones find
 * their position with real GPS; laptops usually guess from WiFi/IP and can
 * be hundreds of meters (sometimes kilometers) off, which is the commonest
 * reason a staff member standing inside the hospital is told they are
 * outside it. On a phone it shrinks to a short reminder. */
export function CheckInPhoneTip() {
  const isTouch = useIsTouchDevice();
  return (
    <div className="gap-space-3 border-brand-100 bg-brand-50 p-space-3 flex items-start rounded-md border">
      <Smartphone size={18} strokeWidth={2} className="text-brand-600 mt-0.5 shrink-0" />
      <div className="text-ink-700 text-[12.5px]">
        <p className="text-ink-900 font-bold">
          {isTouch ? "Tip: keep Location (GPS) turned on" : "Tip: check in from your phone"}
        </p>
        <p className="mt-space-0.5">
          {isTouch
            ? "Allow location access when asked, and stay near a window or outdoors for a few seconds if it's slow."
            : "Phones find your location much more accurately than laptops, so check-in works first time. If you must use this computer, make sure its Location setting is on."}
        </p>
      </div>
    </div>
  );
}

/** Shown when a check-in attempt was refused: what happened, in plain
 * words, and what to do next. */
export function CheckInProblemPanel({
  problem,
  disabled,
  onRetry,
  onRequest,
}: {
  problem: CheckInProblem;
  disabled: boolean;
  onRetry: () => void;
  onRequest: () => void;
}) {
  return (
    <div
      role="alert"
      className="gap-space-3 border-error/30 bg-error-tint p-space-3 flex items-start rounded-md border"
    >
      <XCircle size={18} strokeWidth={2} className="text-error mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-error text-[13px] font-bold">Couldn&apos;t check you in</p>
        <p className="mt-space-1 text-ink-700 text-[12.5px]">{problem.message}</p>
        {problem.code !== "already_checked_in" && (
          <div className="mt-space-3 gap-space-2 flex flex-wrap">
            <Button type="button" onClick={onRetry} disabled={disabled}>
              <MapPin size={13} /> Try again
            </Button>
            {problem.canRequestManual && (
              <Button type="button" variant="secondary" onClick={onRequest}>
                Send check-in request to admin
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** "Waiting for approval" / "your admin declined" for today's request. An
 * approved one needs no banner -- the check-in itself now shows. */
export function CheckInRequestBanner({ request }: { request: CheckInRequest | null }) {
  if (!request || request.status === "approved") return null;
  const pending = request.status === "pending";
  return (
    <div
      className={
        pending
          ? "gap-space-3 border-clay-300 bg-clay-100 p-space-3 flex items-start rounded-md border"
          : "gap-space-3 border-error/30 bg-error-tint p-space-3 flex items-start rounded-md border"
      }
    >
      {pending ? (
        <Clock size={18} strokeWidth={2} className="text-clay-500 mt-0.5 shrink-0" />
      ) : (
        <AlertTriangle size={18} strokeWidth={2} className="text-error mt-0.5 shrink-0" />
      )}
      <div className="text-ink-700 text-[12.5px]">
        <p className="text-ink-900 font-bold">
          {pending
            ? "Your check-in request is waiting for approval"
            : "Your check-in request was declined"}
        </p>
        <p className="mt-space-0.5">
          {pending
            ? `Sent${request.requested_at ? ` at ${formatTimeOnly(request.requested_at)}` : ""}. Your admin will check you in once they approve it -- your check-in time will be the time you asked.`
            : request.review_note
              ? `Your admin said: "${request.review_note}". You can try checking in again or send a new request.`
              : "You can try checking in again or send a new request."}
        </p>
      </div>
    </div>
  );
}

const QUICK_REASONS = [
  "My phone's location isn't working",
  "Hospital WiFi is down",
  "I don't have my phone with me",
];

/** The reason form for a manual check-in request. */
export function CheckInRequestDialog({
  open,
  onClose,
  onSend,
  sending,
  error,
}: {
  open: boolean;
  onClose: () => void;
  onSend: (reason: string) => void;
  sending: boolean;
  error: string | null;
}) {
  const [reason, setReason] = useState("");
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-md">
        <DialogTitle>Send check-in request to your admin</DialogTitle>
        <p className="mb-space-3 text-ink-600 text-[12.5px]">
          Use this only if you are at work but couldn&apos;t check in the normal way. You&apos;re
          not checked in until your admin approves, and your check-in time will be the time you send
          this.
        </p>
        <div className="mb-space-2 gap-space-2 flex flex-wrap">
          {QUICK_REASONS.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setReason(r)}
              className="border-line text-ink-600 hover:border-brand-300 hover:bg-brand-50 px-space-2 h-7 rounded-md border text-[12px] font-semibold"
            >
              {r}
            </button>
          ))}
        </div>
        <Field label="Why couldn't you check in?" required error={error || undefined}>
          <Textarea
            rows={3}
            maxLength={500}
            placeholder="e.g. My phone's location isn't working"
            value={reason}
            invalid={!!error}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        <div className="gap-space-2 flex justify-end">
          <Button type="button" variant="secondary" onClick={onClose} disabled={sending}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => onSend(reason)}
            disabled={sending || reason.trim().length < 5}
          >
            {sending ? "Sending…" : "Send request"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
