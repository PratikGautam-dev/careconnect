import { createContext, useContext } from "react";
import axios, { isAxiosError } from "axios";
import { requestInitToAxiosConfig } from "@/lib/apiClient";
import type { PortalHospital } from "@/lib/portalAuth";

const ACCESS_KEY = "staff_access_token";
const REFRESH_KEY = "staff_refresh_token";
const SESSION_KEY = "staff_session";

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

/** Tokens only -- the live app's session data (name/role/permissions/
 * hospital) is never persisted to localStorage; it's fetched fresh into
 * StaffSessionContext (see StaffSessionProvider) on every /portal/* mount
 * instead. Use this for login/refresh/change-password. */
export function saveStaffTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_KEY, accessToken);
  localStorage.setItem(REFRESH_KEY, refreshToken);
}

/** Tokens AND session, both to localStorage -- kept only because
 * (unused-doctor)/login/page.tsx and useDoctorGuard.ts (reference-only code
 * for a route nobody uses, per the user's own "just for reference" call)
 * still call this exact signature. Nothing in the live app writes
 * SESSION_KEY anymore -- use saveStaffTokens() above instead. */
export function saveStaffSession(accessToken: string, refreshToken: string, session: StaffSession) {
  localStorage.setItem(ACCESS_KEY, accessToken);
  localStorage.setItem(REFRESH_KEY, refreshToken);
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function getStaffAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getStaffRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

/** Reads the localStorage-cached session used by useDoctorGuard.ts; other
 * pages should use useStaffSession() below instead. */
export function getStaffSession(): StaffSession | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearStaffSession() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(SESSION_KEY);
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type FetchResult =
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

/** Attempts one silent refresh via /api/portal/staff/refresh, storing the
 * rotated tokens on success. Returns the new access token, or null if the
 * refresh itself failed (refresh token missing/expired/revoked). Only
 * touches tokens -- StaffSessionContext owns re-fetching session data (name/
 * role/permissions/hospital) on its own schedule, not tied to token refresh. */
async function tryRefresh(): Promise<string | null> {
  const refreshToken = getStaffRefreshToken();
  if (!refreshToken) return null;
  try {
    const res = await axios.post(`${API_BASE_URL}/api/portal/staff/refresh`, {
      refresh_token: refreshToken,
    });
    saveStaffTokens(res.data.access_token, res.data.refresh_token);
    return res.data.access_token as string;
  } catch {
    return null;
  }
}

/** axios wrapper for staff-authenticated requests. Unlike portalFetch
 * (24h shared-hospital token, bare "401 -> logout" is fine there), staff
 * access tokens are ~15min JWTs, so a 401 here first tries ONE silent
 * refresh before giving up and clearing the session -- otherwise routine
 * token expiry during normal use would log people out constantly. */
export async function staffFetch(path: string, init?: RequestInit): Promise<FetchResult> {
  let token = getStaffAccessToken();
  if (!token) return { ok: false, unauthorized: true };

  const config = requestInitToAxiosConfig(init);
  const request = (authToken: string) =>
    axios.request({
      ...config,
      url: `${API_BASE_URL}${path}`,
      headers: { ...config.headers, Authorization: `Bearer ${authToken}` },
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
      clearStaffSession();
      return { ok: false, unauthorized: true };
    }
    try {
      res = await request(token);
    } catch (retryErr) {
      if (!isAxiosError(retryErr) || !retryErr.response) {
        return { ok: false, unauthorized: false, error: "Network error — check your connection." };
      }
      if (retryErr.response.status === 401) {
        clearStaffSession();
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

export type StaffSessionContextValue = {
  session: StaffSession | null;
  error: string | null;
  reload: () => void;
  setSession: (session: StaffSession) => void;
};

/** Populated by StaffSessionProvider (wraps every /portal/* page via
 * app/portal/layout.tsx), which fetches GET /api/portal/staff/me into this
 * on mount and holds it in memory only -- nothing about who's logged in
 * (name/role/permissions/hospital) is ever written to localStorage for the
 * live app anymore. Defaults to `session: null` so a component rendered
 * outside the provider (there shouldn't be one under /portal/*) degrades to
 * the same "no session yet" state every consumer already handles. */
export const StaffSessionContext = createContext<StaffSessionContextValue>({
  session: null,
  error: null,
  reload: () => {},
  setSession: () => {},
});

/** SSR-hydration-safe read of the current staff session: `null` on the
 * server and on the client's first render (StaffSessionProvider's fetch
 * hasn't resolved yet), then the real session an instant later -- same
 * nullable contract the old localStorage-backed version had, so every
 * existing consumer (PortalSidebar, usePermission, PermissionGate, page-
 * level `session?.hospital` reads) needed no changes. */
export function useStaffSession(): StaffSession | null {
  return useContext(StaffSessionContext).session;
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
 * _issue_tokens, shared by both /api/portal/staff/login and /api/portal/
 * staff/refresh) -- already carries everything StaffSession needs, no
 * separate /me fetch required to populate it. */
export type StaffAuthResponse = {
  access_token: string;
  refresh_token: string;
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

/** Reads permissions off the cached session (refreshed on every staff
 * login/refresh). No session -> fails open, same posture as PortalSidebar's
 * pre-existing capability check: the frontend hide is a convenience, the
 * backend's 403 is the real enforcement. A real hook (via useStaffSession)
 * -- call it directly in a component body or inside PermissionGate, never
 * inside a loop/callback (use the plain `hasPermission` function below for
 * that, e.g. NAV_ITEMS.filter in PortalSidebar). */
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
  if (!session) return true;
  return !!session.permissions[pageKey]?.[action];
}
