"use client";

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  StaffSessionContext,
  staffFetch,
  type StaffSession,
  type StaffSessionStatus,
} from "@/lib/staffAuth";
import type { PortalHospital } from "@/lib/portalAuth";

const STAFF_SESSION_QUERY_KEY = ["staff-session"] as const;

// Re-pulls /me (permissions + hospital.admin_capabilities/enabled_features)
// whenever the tab regains focus, so a super-admin's Access Control/Feature
// Toggle change (or a role-permission change) reaches an already-open
// portal tab without the staff member needing to log out or hard-refresh.
// Throttled via `staleTime` below (react-query's own refetchOnWindowFocus
// skips a refetch while the query's data is still "fresh") -- alt-tabbing
// back and forth shouldn't refire this more than once per window.
const FOCUS_RELOAD_MIN_INTERVAL_MS = 15_000;

/** The /me fetch's outcome, kept as data instead of thrown, so a generic
 * (non-auth) failure can leave `status` at "loading" rather than
 * collapsing into react-query's own 'error' status -- see the `status`
 * derivation below for why that distinction matters. */
type SessionQueryResult =
  | { kind: "authenticated"; session: StaffSession }
  | { kind: "unauthenticated" }
  | { kind: "error"; message: string };

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
 * React-Query-backed (queryKey ["staff-session"]) rather than a hand-rolled
 * fetch-inside-a-useEffect: this fetch+setState is exactly the pattern
 * react-hooks/set-state-in-effect flags (calling setState from an effect
 * body causes cascading renders), and there's no way to restructure a
 * genuine "fetch on mount" effect to dodge that rule without either
 * changing behavior or gaming the linter -- see useDoctorDashboard.ts /
 * useStaffDashboard.ts for the same fix applied to plainer data fetches.
 * Two settings here specifically replicate what the old hand-rolled
 * version did that useQuery doesn't do by default:
 *   - `gcTime: 0` -- this provider is the sole reader of this queryKey, so
 *     with gcTime 0 the cache is dropped the instant it has no more
 *     observers (i.e. the moment it unmounts, on navigating out of
 *     /portal/* entirely). Remounting later therefore always starts a
 *     fresh "loading" query and a fresh /me round trip, exactly like the
 *     original per-mount useState did -- never serving a stale cached
 *     session across a full unmount/remount.
 *   - `refetchOnReconnect: false` -- the original never refetched on
 *     network reconnect, only on focus (see FOCUS_RELOAD_MIN_INTERVAL_MS
 *     above) and on explicit `reload()` calls; this keeps that exact
 *     surface instead of picking up react-query's default reconnect
 *     refetch as a bonus nobody asked for. */
export function StaffSessionProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: STAFF_SESSION_QUERY_KEY,
    queryFn: async (): Promise<SessionQueryResult> => {
      const result = await staffFetch("/api/portal/staff/me");
      if (!result.ok) {
        if (result.unauthorized) return { kind: "unauthenticated" };
        return { kind: "error", message: result.error };
      }
      return { kind: "authenticated", session: result.data as StaffSession };
    },
    staleTime: FOCUS_RELOAD_MIN_INTERVAL_MS,
    gcTime: 0,
    refetchOnReconnect: false,
  });

  // On a generic (non-auth) failure, `status` deliberately stays "loading"
  // rather than flipping to "unauthenticated" -- same as the original
  // load()'s `else setError(...)` branch, which never touched `status`
  // either. usePortalGuard only redirects on a CONFIRMED
  // "unauthenticated", so a transient network blip during the mount-time
  // /me call shouldn't bounce an actually-logged-in user to /portal/login.
  const status: StaffSessionStatus =
    !data || data.kind === "error"
      ? "loading"
      : data.kind === "authenticated"
        ? "authenticated"
        : "unauthenticated";
  const session = data?.kind === "authenticated" ? data.session : null;
  const error = data?.kind === "error" ? data.message : null;

  const reload = useCallback(() => {
    queryClient.refetchQueries({ queryKey: STAFF_SESSION_QUERY_KEY });
  }, [queryClient]);

  const setSessionDirectly = useCallback(
    (next: StaffSession) => {
      queryClient.setQueryData<SessionQueryResult>(STAFF_SESSION_QUERY_KEY, () => ({
        kind: "authenticated",
        session: next,
      }));
    },
    [queryClient],
  );

  // Cheap sync path: overwrites only session.hospital, e.g. from
  // usePortalDashboard's already-in-flight 20s poll (its response already
  // embeds _hospital_summary()) -- no extra request, and it's a no-op
  // outside an authenticated session (nothing to patch yet/logged out).
  const patchHospital = useCallback(
    (hospital: PortalHospital) => {
      queryClient.setQueryData<SessionQueryResult>(STAFF_SESSION_QUERY_KEY, (current) =>
        current && current.kind === "authenticated"
          ? { ...current, session: { ...current.session, hospital } }
          : current,
      );
    },
    [queryClient],
  );

  return (
    <StaffSessionContext.Provider
      value={{
        session,
        status,
        error,
        reload,
        setSession: setSessionDirectly,
        patchHospital,
      }}
    >
      {children}
    </StaffSessionContext.Provider>
  );
}
