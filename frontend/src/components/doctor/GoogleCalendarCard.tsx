"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { API_BASE_URL, getStaffAccessToken, staffFetch } from "@/lib/staffAuth";

type CalendarStatus = { configured: boolean; connected: boolean; google_email: string | null };

const CONNECT_ERROR_MESSAGES: Record<string, string> = {
  session_expired: "That took too long — please try connecting again.",
  not_configured: "Google Calendar integration isn't configured yet.",
  google_auth_failed: "Google sign-in didn't complete. Please try again.",
  no_refresh_token: "Google didn't grant the access this needs. Please try again.",
};

// Doctor-schedule page: lets a doctor optionally connect their own Google
// account so tele-consultation bookings create a real Calendar event with a
// Meet link, alongside (not replacing) the existing Jitsi room every doctor
// gets by default. `configured: false` (the real state until the real
// GOOGLE_CALENDAR_CLIENT_ID/SECRET/CALENDAR_TOKEN_ENCRYPTION_KEY are set) is
// a normal, expected state here -- shown as a quiet note, not an error.
export function GoogleCalendarCard() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/doctor/calendar/status");
    if (result.ok) setStatus(result.data as CalendarStatus);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDisconnect() {
    setDisconnecting(true);
    await staffFetch("/api/doctor/calendar/disconnect", { method: "POST" });
    setDisconnecting(false);
    load();
  }

  function handleConnect() {
    const token = getStaffAccessToken();
    if (!token) {
      setError("Session expired — please log in again.");
      return;
    }
    // A full-page navigation, not a fetch -- Google's OAuth consent screen
    // requires a real browser redirect, so the doctor's access token travels
    // as a query param here (the only way to identify them on a plain <a>-
    // style navigation), same as auth/google_oauth.py's own callback
    // delivers ITS tokens back via redirect query params in the other
    // direction.
    window.location.href = `${API_BASE_URL}/auth/google/calendar/connect?token=${encodeURIComponent(token)}`;
  }

  const calendarParam = searchParams.get("calendar");
  const calendarErrorParam = searchParams.get("calendar_error");

  return (
    <Card className="p-space-5">
      <p className="text-label mb-space-1 font-semibold text-ink-900">Google Meet for tele-consultations</p>
      <p className="mb-space-3 text-[12.5px] text-ink-600">
        Connect your Google account so a tele-consultation booking creates a real Google Calendar event with a Meet
        link, instead of the default video room.
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
        <p className="text-[12.5px] text-ink-400">
          Google Calendar integration isn&apos;t configured yet — ask your hospital administrator.
        </p>
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
    </Card>
  );
}
