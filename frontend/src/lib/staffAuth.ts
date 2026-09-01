import axios, { isAxiosError } from "axios";
import { requestInitToAxiosConfig } from "@/lib/apiClient";
import type { PortalHospital } from "@/lib/portalAuth";

const ACCESS_KEY = "staff_access_token";
const REFRESH_KEY = "staff_refresh_token";
const SESSION_KEY = "staff_session";

export type StaffRole = "admin" | "receptionist" | "doctor";
export type StaffPermissions = Record<string, { view: boolean; write: boolean; delete: boolean }>;

export type StaffSession = {
  id: number;
  name: string;
  role: StaffRole;
  hospital: PortalHospital;
  permissions: StaffPermissions;
};

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type FetchResult =
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

/** Attempts one silent refresh via /api/portal/staff/refresh, storing the
 * rotated tokens on success. Returns the new access token, or null if the
 * refresh itself failed (refresh token missing/expired/revoked). */
async function tryRefresh(): Promise<string | null> {
  const refreshToken = getStaffRefreshToken();
  if (!refreshToken) return null;
  try {
    const res = await axios.post(`${API_BASE_URL}/api/portal/staff/refresh`, { refresh_token: refreshToken });
    const data = res.data;
    const existing = getStaffSession();
    const session: StaffSession = {
      id: data.staff.id,
      name: data.staff.name,
      role: data.staff.role,
      hospital: data.staff.hospital || existing?.hospital,
      permissions: data.permissions,
    };
    saveStaffSession(data.access_token, data.refresh_token, session);
    return data.access_token as string;
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
      return { ok: false, unauthorized: false, error: err.response.data?.error || "Something went wrong." };
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
      return { ok: false, unauthorized: false, error: retryErr.response.data?.error || "Something went wrong." };
    }
  }

  return { ok: true, data: res.data };
}

/** Reads permissions off the cached session (refreshed on every staff
 * login/refresh). No session -> fails open, same posture as PortalSidebar's
 * pre-existing capability check: the frontend hide is a convenience, the
 * backend's 403 is the real enforcement.
 *
 * Not a real React hook (no internal state/effects) -- it's just a plain
 * localStorage read wearing the `use`-prefixed name the plan doc specifies.
 * Call it directly in a component body or inside PermissionGate as intended;
 * use the `hasPermission` alias below when calling it from a loop/callback
 * (e.g. NAV_ITEMS.filter in PortalSidebar) so eslint's rules-of-hooks check
 * -- which goes purely off the `use`-prefix -- doesn't flag it. */
export function usePermission(pageKey: string, action: "view" | "write" | "delete"): boolean {
  const session = getStaffSession();
  if (!session) return true;
  return !!session.permissions[pageKey]?.[action];
}

export const hasPermission = usePermission;
