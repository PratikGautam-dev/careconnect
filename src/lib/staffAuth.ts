import { createContext, useContext } from "react";
import axios, { isAxiosError } from "axios";
import { requestInitToAxiosConfig } from "@/lib/apiClient";
import { PAGE_CAPABILITY } from "@/lib/hospitalCapabilities";
import type { PortalHospital } from "@/lib/portalAuth";

// Roles are admin-defined per hospital; see usePortalRoles.ts's Role type for the fetched shape.
export type StaffPermissions = Record<string, { view: boolean; write: boolean; delete: boolean }>;

export type StaffSession = {
  id: number;
  name: string;
  role_id: number;
  role_name: string;
  // Whether this login is linked to a doctor profile (doctor_id !== null,
  // computed backend-side) -- a per-staff attribute, not a role property:
  // any role can optionally have a doctor linked. Every `role === "doctor"`
  // UI branch switches to this instead of a role-name comparison.
  is_doctor_role: boolean;
  // RoleRow.is_protected on the backend -- true only for the hospital's
  // seeded Admin role, a structural flag that survives that role being
  // renamed (unlike comparing role_name === "Admin"). Used to pick which
  // dashboard variant to render.
  is_admin: boolean;
  doctor_id: string | null;
  hospital: PortalHospital;
  permissions: StaffPermissions;
};

/** The access token lives ONLY in this module-level variable, never in
 * localStorage/sessionStorage/a cookie readable by JS -- an XSS payload
 * can still steal it while it's live in a tab, but it can't persist that
 * theft past a page reload the way reading it out of localStorage would.
 * The refresh token is never handled by JS at all anymore: the backend
 * sets/reads it as an httpOnly cookie (auth/refresh_cookie.py), scoped to
 * /api/portal/staff, invisible to document.cookie/localStorage/every other
 * JS-readable surface -- see that module's own docstring for the full
 * reasoning. Lost on every full page reload by design: tryRefresh() below
 * re-mints one from the refresh cookie automatically the next time
 * staffFetch needs one, same round trip StaffSessionProvider already pays
 * on mount. */
let _accessToken: string | null = null;

export function getStaffAccessToken(): string | null {
  return _accessToken;
}

export function setStaffAccessToken(token: string | null) {
  _accessToken = token;
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type FetchResult =
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

/** Coalesces concurrent tryRefresh() callers onto ONE in-flight request --
 * see tryRefresh()'s own docstring for why this exists: without it, every
 * staffFetch call that happens to race in at once (e.g. a fresh page load,
 * where the dashboard, the calendar, StaffSessionProvider's /me, etc. all
 * fire in the same tick) independently notices "no access token yet" and
 * independently calls the refresh endpoint. The refresh token is single-
 * use (deleted the instant it's consumed -- auth/refresh_tokens.py's
 * rotation), so of N simultaneous callers presenting the SAME
 * not-yet-rotated cookie, exactly one gets a 200 and every other one gets
 * a 401 and (wrongly) concludes the session is dead. Storing the in-flight
 * promise here means every caller within that window awaits the SAME
 * request/result instead of each starting their own. */
let _refreshInFlight: Promise<string | null> | null = null;

/** Attempts one silent refresh via /api/portal/staff/refresh, storing the
 * new access token in memory on success. The refresh token itself is never
 * touched here -- it's an httpOnly cookie the browser attaches
 * automatically (credentials: "include"); this call doesn't and can't read
 * it. X-Requested-With is a cheap CSRF guard the backend requires on this
 * specific endpoint (see staff_auth.py's staff_refresh docstring) -- a
 * plain cross-site <form>/no-JS request can't set custom headers, so it
 * can never reach this endpoint at all. Returns the new access token, or
 * null if the refresh itself failed (refresh cookie missing/expired/
 * revoked). Only touches the token -- StaffSessionContext owns re-fetching
 * session data (name/role/permissions/hospital) on its own schedule, not
 * tied to token refresh. */
function tryRefresh(): Promise<string | null> {
  if (_refreshInFlight) return _refreshInFlight;

  _refreshInFlight = (async () => {
    try {
      const res = await axios.post(
        `${API_BASE_URL}/api/portal/staff/refresh`,
        {},
        { withCredentials: true, headers: { "X-Requested-With": "XMLHttpRequest" } },
      );
      setStaffAccessToken(res.data.access_token);
      return res.data.access_token as string;
    } catch {
      return null;
    } finally {
      // Cleared once this round settles (success or failure), not kept
      // around -- the NEXT time a token's needed (natural 15-min expiry,
      // another hard reload) must start a fresh request, not replay this
      // one's now-stale result.
      _refreshInFlight = null;
    }
  })();

  return _refreshInFlight;
}

/** axios wrapper for staff-authenticated requests. Unlike portalFetch
 * (24h shared-hospital token, bare "401 -> logout" is fine there), staff
 * access tokens are ~15min JWTs living only in memory (lost on every page
 * reload), so this ALWAYS tries a silent refresh first when there's no
 * token on hand yet, and again on a 401 mid-session, before giving up --
 * otherwise a fresh page load (or routine token expiry during normal use)
 * would look indistinguishable from being logged out. */
export async function staffFetch(path: string, init?: RequestInit): Promise<FetchResult> {
  let token = getStaffAccessToken();
  if (!token) {
    token = await tryRefresh();
    if (!token) return { ok: false, unauthorized: true };
  }

  const config = requestInitToAxiosConfig(init);
  const request = (authToken: string) =>
    axios.request({
      ...config,
      url: `${API_BASE_URL}${path}`,
      headers: { ...config.headers, Authorization: `Bearer ${authToken}` },
      // Most staffFetch calls don't touch the refresh cookie at all (it's
      // scoped to /api/portal/staff, and the backend only sets/reads it on
      // login/refresh/logout/change-password) -- but change-password DOES
      // set a fresh one on its response, and without withCredentials the
      // browser silently discards that Set-Cookie instead of storing it.
      // Harmless to set unconditionally: a request outside that cookie's
      // path just has nothing to send.
      withCredentials: true,
    });

  let res;
  try {
    res = await request(token);
  } catch (err) {
    if (!isAxiosError(err) || !err.response) {
      return { ok: false, unauthorized: false, error: "Network error — check your connection." };
    }
    if (err.response.status !== 401) {
      return {
        ok: false,
        unauthorized: false,
        error: err.response.data?.error || "Something went wrong.",
      };
    }

    token = await tryRefresh();
    if (!token) {
      setStaffAccessToken(null);
      return { ok: false, unauthorized: true };
    }
    try {
      res = await request(token);
    } catch (retryErr) {
      if (!isAxiosError(retryErr) || !retryErr.response) {
        return { ok: false, unauthorized: false, error: "Network error — check your connection." };
      }
      if (retryErr.response.status === 401) {
        setStaffAccessToken(null);
        return { ok: false, unauthorized: true };
      }
      return {
        ok: false,
        unauthorized: false,
        error: retryErr.response.data?.error || "Something went wrong.",
      };
    }
  }

  return { ok: true, data: res.data };
}

/** Revokes the refresh cookie server-side and clears it, then drops the
 * in-memory access token. MUST hit the backend now (unlike the old
 * localStorage-only version) -- an httpOnly cookie can't be cleared by
 * page JS, only by the server responding with an expired Set-Cookie, so
 * skipping this call would leave a still-live refresh token sitting in the
 * browser indefinitely. Safe to call even with no session (e.g. an already
 * -expired/never-had one); the backend logout route doesn't require a
 * valid access token either, for the same "must still succeed on the way
 * out" reasoning. */
export async function clearStaffSession(): Promise<void> {
  setStaffAccessToken(null);
  try {
    await axios.post(`${API_BASE_URL}/api/portal/staff/logout`, {}, { withCredentials: true });
  } catch {
    // Best-effort -- the in-memory token is already cleared either way, and
    // a network failure here shouldn't block the user from navigating away.
  }
}

export type StaffSessionStatus = "loading" | "authenticated" | "unauthenticated";

export type StaffSessionContextValue = {
  session: StaffSession | null;
  status: StaffSessionStatus;
  error: string | null;
  reload: () => void;
  setSession: (session: StaffSession) => void;
  patchHospital: (hospital: PortalHospital) => void;
};

/** Populated by StaffSessionProvider (wraps every /portal/* page via
 * app/portal/layout.tsx), which fetches GET /api/portal/staff/me into this
 * on mount and holds it in memory only -- nothing about who's logged in
 * (name/role/permissions/hospital) is ever written to localStorage.
 * `status` starts "loading" (server render and the client's first paint
 * both see this) so consumers can distinguish "we don't know yet" from
 * "confirmed logged out" -- see hasPermission's own docstring for why that
 * distinction is what fixes the old "full sidebar flashes, then narrows"
 * bug, and usePortalGuard.ts for why it's also what stops a page reload
 * from bouncing a still-logged-in user to /portal/login. */
export const StaffSessionContext = createContext<StaffSessionContextValue>({
  session: null,
  status: "loading",
  error: null,
  reload: () => {},
  setSession: () => {},
  patchHospital: () => {},
});

/** SSR-hydration-safe read of the current staff session: `null` on the
 * server and on the client's first render (StaffSessionProvider's fetch
 * hasn't resolved yet), then the real session an instant later. */
export function useStaffSession(): StaffSession | null {
  return useContext(StaffSessionContext).session;
}

/** "loading" until the initial /me (+ silent-refresh-if-needed) round trip
 * resolves one way or the other. Consumers that need to tell "still
 * figuring it out" apart from "definitely not logged in" (usePortalGuard's
 * redirect, PortalSidebar's nav gating) should read this instead of just
 * checking `session === null`, which is also true during "loading". */
export function useStaffSessionStatus(): StaffSessionStatus {
  return useContext(StaffSessionContext).status;
}

/** The session context's own refetch -- call right after a successful
 * login so the already-mounted StaffSessionProvider (shared across every
 * /portal/* page via app/portal/layout.tsx, including /portal/login
 * itself) picks up the just-saved token immediately. A plain client-side
 * router.push() into /portal/dashboard does NOT remount that provider
 * (same layout subtree, so its mount-time fetch doesn't re-run) -- without
 * this, session stays stuck at the unauthenticated `null` its very first
 * mount (before login even happened) already resolved to, until a manual
 * full page refresh forces a fresh mount with the token already present. */
export function useStaffSessionReload(): () => void {
  return useContext(StaffSessionContext).reload;
}

/** Login/refresh response shape (backend's portal/routes/staff_auth.py::
 * _issue_tokens, shared by /api/portal/staff/login and /api/portal/staff/
 * refresh) -- already carries everything StaffSession needs, no separate
 * /me fetch required to populate it. No refresh_token field anymore -- the
 * backend sets that as an httpOnly cookie on the response instead of
 * returning it in the body (see auth/refresh_cookie.py). */
export type StaffAuthResponse = {
  access_token: string;
  staff: {
    id: number;
    name: string;
    role_id: number;
    role_name: string;
    is_doctor_role: boolean;
    is_admin: boolean;
    doctor_id: string | null;
    hospital: PortalHospital;
  };
  permissions: StaffPermissions;
};

export function staffSessionFromAuthResponse(data: StaffAuthResponse): StaffSession {
  return {
    id: data.staff.id,
    name: data.staff.name,
    role_id: data.staff.role_id,
    role_name: data.staff.role_name,
    is_doctor_role: data.staff.is_doctor_role,
    is_admin: data.staff.is_admin,
    doctor_id: data.staff.doctor_id,
    hospital: data.staff.hospital,
    permissions: data.permissions,
  };
}

/** Seeds StaffSessionContext synchronously -- call right after a login/
 * refresh response comes back (via staffSessionFromAuthResponse above), so
 * the already-mounted StaffSessionProvider (shared across every /portal/*
 * page via app/portal/layout.tsx, including /portal/login itself) has the
 * real session BEFORE navigating into the portal, instead of racing a
 * second /me round-trip after the navigation (the "dashboard/sidebar
 * render ungated, then pop into their real per-role state a moment later"
 * flash this replaces -- see useStaffSessionReload's own docstring for why
 * a plain client-side router.push() alone never re-fetches it). */
export function useSetStaffSession(): (session: StaffSession) => void {
  return useContext(StaffSessionContext).setSession;
}

/** Overwrites just `session.hospital` in place, without a full /me
 * round-trip -- the cheap path back into the shared session for callers
 * that already received a fresher copy of the hospital (admin_capabilities/
 * enabled_features) as a side effect of some other request, e.g.
 * usePortalDashboard's 20s poll, whose response already embeds
 * _hospital_summary(). Lets an admin's Access Control change reach the
 * sidebar/nav without waiting for the next full session reload. */
export function useStaffSessionPatchHospital(): (hospital: PortalHospital) => void {
  return useContext(StaffSessionContext).patchHospital;
}

/** Reads permissions off the cached session (refreshed on every staff
 * login/refresh). No session -> fails CLOSED (hides the item) rather than
 * open: while StaffSessionProvider's initial /me (+ silent-refresh) round
 * trip is still in flight, `session` is `null` the same way it is once
 * we've confirmed the caller is logged out, and there's no way to tell
 * those two apart from `session` alone -- failing open there is what
 * rendered the full, unfiltered nav for every role on first paint before
 * narrowing down to the real per-role set a moment later. Failing closed
 * instead means a not-yet-resolved session briefly shows nothing/less
 * rather than everything; the backend's 403 remains the actual
 * enforcement either way, this is still only a UI convenience. A real hook
 * (via useStaffSession) -- call it directly in a component body or inside
 * PermissionGate, never inside a loop/callback (use the plain
 * `hasPermission` function below for that, e.g. NAV_ITEMS.filter in
 * PortalSidebar). */
export function usePermission(pageKey: string, action: "view" | "write" | "delete"): boolean {
  const session = useStaffSession();
  return hasPermission(session, pageKey, action);
}

/** Same permission check as usePermission, but a plain function taking an
 * already-resolved session instead of reading one itself -- safe to call
 * from inside a loop/callback (e.g. NAV_ITEMS.filter in PortalSidebar),
 * which a real hook (usePermission above) cannot be, since hook call count/
 * order must stay fixed across renders. Callers get `session` once, from
 * their own top-level useStaffSession() call, and pass it in here per item. */
export function hasPermission(
  session: StaffSession | null,
  pageKey: string,
  action: "view" | "write" | "delete",
): boolean {
  if (!session) return false;
  return !!session.permissions[pageKey]?.[action];
}

/** Same idea as hasPermission, but checks the hospital's tenant-level
 * admin_capabilities (Access Control, super-admin-only) instead of a
 * staff member's per-role permissions -- a hospital can have every staff
 * permission granted and still not see a screen the platform admin turned
 * off for its tenant/plan. Fails CLOSED (hides the item) while the session
 * hasn't loaded yet, same reasoning as hasPermission. Pages with no entry
 * in PAGE_CAPABILITY are unaffected (always passes). */
export function hasCapability(session: StaffSession | null, pageKey: string): boolean {
  const capability = PAGE_CAPABILITY[pageKey];
  if (!capability) return true;
  if (!session) return false;
  return !!session.hospital.admin_capabilities?.includes(capability);
}
