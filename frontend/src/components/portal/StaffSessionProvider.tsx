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
 * /portal/login. */
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
    <StaffSessionContext.Provider value={{ session, error, reload: load }}>
      {children}
    </StaffSessionContext.Provider>
  );
}
