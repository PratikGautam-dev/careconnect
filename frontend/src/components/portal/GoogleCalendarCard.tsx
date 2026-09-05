"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { API_BASE_URL, getStaffAccessToken, staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

type CalendarStatus = { configured: boolean; connected: boolean; google_email: string | null };

const CONNECT_ERROR_MESSAGES: Record<string, string> = {
  session_expired: "That took too long — please try connecting again.",
  not_configured: "Google Calendar integration isn't configured yet.",
  google_auth_failed: "Google sign-in didn't complete. Please try again.",
  no_refresh_token: "Google didn't grant the access this needs. Please try again.",
};

// Hospital Settings page, admin-only: connects ONE Google account for the
// whole hospital (not a per-doctor connection) so every doctor's
// tele-consultation bookings create a real Calendar event with a Meet
// link, alongside (not replacing) the default video room every hospital
// already gets. `configured: false` (the real state until the real
// GOOGLE_CALENDAR_CLIENT_ID/SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY are set) is
// a normal, expected state here -- shown as a quiet note, not an error.
export function GoogleCalendarCard() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/calendar/status");
    if (result.ok) setStatus(result.data as CalendarStatus);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // The connect flow is a full-page redirect back here with ?calendar=
  // connected -- the only place that success can be reported from, so it's
  // toasted once on arrival rather than from a normal fetch call site.
  useEffect(() => {
    if (searchParams.get("calendar") === "connected") toast.success("Google Calendar connected");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleDisconnect() {
    setDisconnecting(true);
    const result = await staffFetch("/api/portal/calendar/disconnect", { method: "POST" });
    setDisconnecting(false);
    if (result.ok) {
      toast.success("Google Calendar disconnected");
    } else if (!result.unauthorized) {
      toast.error("Couldn't disconnect Google Calendar", result.error);
    }
    load();
  }

  function handleConnect() {
    const token = getStaffAccessToken();
    if (!token) {
      setError("Session expired — please log in again.");
      return;
    }
    // A full-page navigation, not a fetch -- Google's OAuth consent screen
    // requires a real browser redirect, so the admin's access token travels
    // as a query param here (the only way to identify them on a plain <a>-
    // style navigation), same as auth/google_oauth.py's own callback
    // delivers ITS tokens back via redirect query params in the other
    // direction.
    window.location.href = `${API_BASE_URL}/auth/google/calendar/connect?token=${encodeURIComponent(token)}`;
  }

  const calendarParam = searchParams.get("calendar");
  const calendarErrorParam = searchParams.get("calendar_error");

  return (
    <>
      <h2 className="mb-space-1 text-[15px] font-bold text-ink-900">Google Meet for tele-consultations</h2>
      <p className="mb-space-3 text-[12.5px] text-ink-400">
        Connect one Google account for your hospital so every doctor&apos;s tele-consultation bookings create a real
        Google Calendar event with a Meet link, instead of the default video room. This is a hospital-wide
        connection, made once by an admin — individual doctors don&apos;t connect their own accounts.
      </p>

      {calendarParam === "connected" && (
        <p className="mb-space-3 text-[12.5px] font-semibold text-success">Google Calendar connected.</p>
      )}
      {calendarErrorParam && (
        <p className="mb-space-3 text-[12.5px] text-error">
          {CONNECT_ERROR_MESSAGES[calendarErrorParam] || "Something went wrong connecting Google Calendar."}
        </p>
      )}
      {error && <p className="mb-space-3 text-[12.5px] text-error">{error}</p>}

      {status === null ? (
        <p className="text-[12.5px] text-ink-400">Loading…</p>
      ) : !status.configured ? (
        <p className="text-[12.5px] text-ink-400">Google Calendar integration isn&apos;t configured yet.</p>
      ) : status.connected ? (
        <div className="flex flex-wrap items-center justify-between gap-space-3">
          <p className="text-[13px] text-ink-900">
            Connected as <span className="font-semibold">{status.google_email}</span>
          </p>
          <Button variant="secondary" size="md" onClick={handleDisconnect} disabled={disconnecting}>
            {disconnecting ? "Disconnecting…" : "Disconnect"}
          </Button>
        </div>
      ) : (
        <Button size="md" onClick={handleConnect}>
          Connect Google Calendar
        </Button>
      )}
    </>
  );
}
