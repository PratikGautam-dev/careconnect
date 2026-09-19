"use client";

import { useCallback, useEffect, useState } from "react";
import { StaffSessionContext, staffFetch, type StaffSession } from "@/lib/staffAuth";

/** Wraps every /portal/* page (app/portal/layout.tsx) and fetches GET
 * /api/portal/staff/me once per mount into StaffSessionContext -- the
 * in-memory replacement for the old localStorage-cached staff_session.
 * Doesn't redirect on failure/401 -- each page's own staffFetch call
 * already owns that; a session-less render here just means every consumer
 * sees `session: null` (usePermission/hasPermission both fail open in that
 * state) until either the fetch resolves or the page itself bounces to
 * /portal/login.
 *
 * Also exposes `setSession` (see useSetStaffSession) so the login page can
 * seed this context SYNCHRONOUSLY from its own login response -- that
 * response already carries the full staff+permissions shape (issue_tokens()
 * on the backend, shared by login/refresh), so there's no need to wait on a
 * second /me round-trip (and the "sidebar/dashboard render ungated, then
 * pop into their real per-role state a moment later" flash that caused)
 * before navigating into the portal. */
export function StaffSessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<StaffSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/staff/me");
    if (!result.ok) {
      if (!result.unauthorized) setError(result.error);
      return;
    }
    setSession(result.data as StaffSession);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <StaffSessionContext.Provider value={{ session, error, reload: load, setSession }}>
      {children}
    </StaffSessionContext.Provider>
  );
}
