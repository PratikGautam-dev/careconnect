"use client";

import { useCallback, useEffect, useState } from "react";
import {
  StaffSessionContext,
  staffFetch,
  type StaffSession,
  type StaffSessionStatus,
} from "@/lib/staffAuth";

/** Wraps every /portal/* page (app/portal/layout.tsx) and fetches GET
 * /api/portal/staff/me once per mount into StaffSessionContext -- the
 * in-memory replacement for the old localStorage-cached staff_session.
 * That fetch itself now silently tries the refresh cookie first if there's
 * no access token in memory yet (staffFetch's own logic), which is the
 * normal case on every fresh page load since the access token lives only
 * in memory (see staffAuth.ts's own module docstring) -- so this is also
 * what re-establishes a session after a hard refresh, not just the initial
 * login.
 *
 * `status` starts "loading" and moves to "authenticated" or
 * "unauthenticated" once that round trip resolves -- consumers that need
 * to tell "still figuring it out" apart from "confirmed logged out"
 * (usePortalGuard's redirect, PortalSidebar's hasPermission gating) read
 * this instead of just `session === null`, which is also true while
 * loading. Doesn't redirect on unauthenticated itself -- usePortalGuard.ts
 * (and each page's own staffFetch calls) own that.
 *
 * Also exposes `setSession` (see useSetStaffSession) so the login page can
 * seed this context SYNCHRONOUSLY from its own login response -- that
 * response already carries the full staff+permissions shape (issue_tokens()
 * on the backend, shared by login/refresh), so there's no need to wait on a
 * second /me round-trip before navigating into the portal. */
export function StaffSessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<StaffSession | null>(null);
  const [status, setStatus] = useState<StaffSessionStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/staff/me");
    if (!result.ok) {
      if (result.unauthorized) {
        setSession(null);
        setStatus("unauthenticated");
      } else {
        setError(result.error);
      }
      return;
    }
    setSession(result.data as StaffSession);
    setStatus("authenticated");
    setError(null);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setSessionDirectly = useCallback((next: StaffSession) => {
    setSession(next);
    setStatus("authenticated");
  }, []);

  return (
    <StaffSessionContext.Provider
      value={{ session, status, error, reload: load, setSession: setSessionDirectly }}
    >
      {children}
    </StaffSessionContext.Provider>
  );
}
