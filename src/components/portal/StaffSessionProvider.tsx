"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  StaffSessionContext,
  staffFetch,
  type StaffSession,
  type StaffSessionStatus,
} from "@/lib/staffAuth";
import type { PortalHospital } from "@/lib/portalAuth";

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
  const lastLoadAt = useRef(0);

  const load = useCallback(async () => {
    lastLoadAt.current = Date.now();
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

  // Re-pulls /me (permissions + hospital.admin_capabilities/enabled_features)
  // whenever the tab regains focus, so a super-admin's Access Control/
  // Feature Toggle change (or a role-permission change) reaches an
  // already-open portal tab without the staff member needing to log out or
  // hard-refresh. Throttled -- alt-tabbing back and forth shouldn't refire
  // this more than once per short window.
  const FOCUS_RELOAD_MIN_INTERVAL_MS = 15_000;
  useEffect(() => {
    function onFocus() {
      if (Date.now() - lastLoadAt.current < FOCUS_RELOAD_MIN_INTERVAL_MS) return;
      load();
    }
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  const setSessionDirectly = useCallback((next: StaffSession) => {
    setSession(next);
    setStatus("authenticated");
  }, []);

  // Cheap sync path: overwrites only session.hospital, e.g. from
  // usePortalDashboard's already-in-flight 20s poll (its response already
  // embeds _hospital_summary()) -- no extra request, and it's a no-op
  // outside an authenticated session (nothing to patch yet/logged out).
  const patchHospital = useCallback((hospital: PortalHospital) => {
    setSession((current) => (current ? { ...current, hospital } : current));
  }, []);

  return (
    <StaffSessionContext.Provider
      value={{
        session,
        status,
        error,
        reload: load,
        setSession: setSessionDirectly,
        patchHospital,
      }}
    >
      {children}
    </StaffSessionContext.Provider>
  );
}
