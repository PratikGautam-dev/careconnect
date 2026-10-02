import { useState } from "react";
import { getBestPosition, type PositionResult } from "@/lib/getBestPosition";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import type { AttendanceRecord } from "@/hooks/usePortalAttendanceToday";

const CHECK_IN_PATH = "/api/portal/attendance/check-in";
const CHECK_OUT_PATH = "/api/portal/attendance/check-out";

/** What went wrong with a check-in attempt, in words meant for the staff
 * member -- the page shows this inline (with the next steps) instead of a
 * toast that disappears before it can be read. */
export type CheckInProblem = {
  message: string;
  code: string | null;
  canRequestManual: boolean;
};

function locationBody(position: PositionResult) {
  return position.ok
    ? {
        latitude: position.reading.latitude,
        longitude: position.reading.longitude,
        accuracy: position.reading.accuracy,
      }
    : {};
}

/** The Check In / Check Out / break buttons' shared behavior for every page
 * that has them (the check-in page and the staff dashboard), including the
 * accurate-location capture, the plain-language failure panel, and the
 * "send my admin a check-in request" fallback. */
export function useCheckInActions({
  onChanged,
  onCheckedIn,
}: {
  onChanged: () => Promise<unknown> | void;
  onCheckedIn?: (record: AttendanceRecord) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [problem, setProblem] = useState<CheckInProblem | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [sendingRequest, setSendingRequest] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  // The reading from the failed attempt, so the admin sees where the staff
  // member actually was when they asked.
  const [lastPosition, setLastPosition] = useState<PositionResult | null>(null);

  async function checkIn() {
    setBusy(true);
    setProblem(null);
    setLocating(true);
    const position = await getBestPosition();
    setLocating(false);
    setLastPosition(position);
    const result = await staffFetch(CHECK_IN_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(locationBody(position)),
    });
    setBusy(false);
    if (!result.ok) {
      if (result.unauthorized) {
        toast.error("That didn't go through", "Please sign in again.");
        return;
      }
      const body = result.body ?? {};
      setProblem({
        message: result.error,
        code: typeof body.code === "string" ? body.code : null,
        canRequestManual: body.can_request_manual === true,
      });
      if (body.code === "already_checked_in") await onChanged();
      return;
    }
    await onChanged();
    onCheckedIn?.((result.data as { record: AttendanceRecord }).record);
  }

  async function checkOut() {
    setBusy(true);
    // Only recorded, never checked -- so don't make someone going home wait
    // long for a precise fix.
    const position = await getBestPosition({ maxWaitMs: 4_000, goodEnoughMeters: 100 });
    const result = await staffFetch(CHECK_OUT_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(locationBody(position)),
    });
    setBusy(false);
    if (!result.ok) {
      toast.error(
        "That didn't go through",
        result.unauthorized ? "Please sign in again." : result.error,
      );
      return;
    }
    await onChanged();
  }

  /** Break start/end -- plain POSTs with no location. */
  async function simpleAction(path: string) {
    setBusy(true);
    const result = await staffFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    setBusy(false);
    if (!result.ok) {
      toast.error(
        "That didn't go through",
        result.unauthorized ? "Please sign in again." : result.error,
      );
      return;
    }
    await onChanged();
  }

  async function sendRequest(reason: string) {
    setSendingRequest(true);
    setRequestError(null);
    const result = await staffFetch("/api/portal/attendance/check-in/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reason,
        failure_reason: problem?.message ?? "",
        ...(lastPosition ? locationBody(lastPosition) : {}),
      }),
    });
    setSendingRequest(false);
    if (!result.ok) {
      setRequestError(result.unauthorized ? "Please sign in again." : result.error);
      return;
    }
    setRequestOpen(false);
    setProblem(null);
    toast.success("Request sent", "Your admin will review it and check you in.");
    await onChanged();
  }

  return {
    busy,
    locating,
    problem,
    dismissProblem: () => setProblem(null),
    checkIn,
    checkOut,
    simpleAction,
    requestOpen,
    openRequest: () => {
      setRequestError(null);
      setRequestOpen(true);
    },
    closeRequest: () => setRequestOpen(false),
    sendRequest,
    sendingRequest,
    requestError,
  };
}
