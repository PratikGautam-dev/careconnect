// Platform-admin (tenant list/edit) auth -- deliberately separate from
// lib/portalAuth.ts's hospital-staff session. Was a shared TENANTS_ADMIN_SECRET
// header; now an individually-issued super-admin JWT from
// POST /api/admin/super/login, so tenant-data access has a real audit trail.
// Stored in sessionStorage (not localStorage): deliberately given the
// shorter lifetime/exposure of a single tab session.

const TOKEN_KEY = "super_admin_token";
const ADMIN_KEY = "super_admin";

export type SuperAdmin = { id: number; name: string; email: string };

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getSuperAdmin(): SuperAdmin | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(ADMIN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setAdminToken(token: string, admin: SuperAdmin) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(ADMIN_KEY, JSON.stringify(admin));
}

export function clearAdminToken() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ADMIN_KEY);
}

import axios, { isAxiosError } from "axios";
import { blobErrorToMessage, requestInitToAxiosConfig } from "@/lib/apiClient";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** Coalesces concurrent refreshes onto ONE request -- the refresh token is
 * single-use (rotated), so of N calls racing in at once with the same
 * cookie only one would succeed and the rest would wrongly conclude the
 * session is dead. Same reasoning as staffAuth.ts's tryRefresh. */
let _refreshInFlight: Promise<string | null> | null = null;

/** Silent sign-in from the httpOnly refresh cookie (12-hour lifetime, set at
 * login and rotated on every use -- admin/super_auth.py). Stores the new
 * short-lived access token like a normal login and returns it, or null when
 * there's no valid cookie (never signed in, expired, logged out, password
 * changed elsewhere). X-Requested-With is the cheap CSRF guard the backend
 * requires on this endpoint. */
export function tryAdminRefresh(): Promise<string | null> {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = (async () => {
    try {
      const res = await axios.post(
        `${API_BASE_URL}/api/admin/super/refresh`,
        {},
        { withCredentials: true, headers: { "X-Requested-With": "XMLHttpRequest" } },
      );
      setAdminToken(res.data.access_token, res.data.super_admin);
      return res.data.access_token as string;
    } catch {
      return null;
    } finally {
      _refreshInFlight = null;
    }
  })();
  return _refreshInFlight;
}

/** Signs out: revokes this browser's refresh token on the server (the
 * httpOnly cookie can only be cleared by the server) and drops the local
 * session. Best-effort -- a network failure still signs out locally. */
export async function adminLogout(): Promise<void> {
  try {
    await axios.post(`${API_BASE_URL}/api/admin/super/logout`, {}, { withCredentials: true });
  } catch {
    // Local sign-out below still happens.
  }
  clearAdminToken();
}

export async function adminFetch(
  path: string,
  init?: RequestInit,
): Promise<
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string }
> {
  // No token in this tab (new tab, token expired and was dropped) -> try the
  // refresh cookie before treating it as signed out.
  let token = getAdminToken() ?? (await tryAdminRefresh());
  if (!token) return { ok: false, unauthorized: true };

  for (let attempt = 0; ; attempt++) {
    try {
      const res = await axios.request({
        ...requestInitToAxiosConfig(init),
        // Lets the browser accept the rotated refresh cookie that
        // POST /api/admin/super/change-password sets (the cookie is path-
        // scoped to /api/admin/super, so it's never sent to other routes).
        withCredentials: true,
        url: `${API_BASE_URL}${path}`,
        headers: { ...requestInitToAxiosConfig(init).headers, Authorization: `Bearer ${token}` },
      });
      return { ok: true, data: res.data };
    } catch (err) {
      if (isAxiosError(err) && err.response) {
        if (err.response.status === 401) {
          clearAdminToken();
          // Access token expired mid-session: renew once and retry.
          const fresh = attempt === 0 ? await tryAdminRefresh() : null;
          if (fresh) {
            token = fresh;
            continue;
          }
          return { ok: false, unauthorized: true };
        }
        const data = err.response.data;
        return {
          ok: false,
          unauthorized: false,
          error: data?.error || (data?.errors || []).join(" ") || "Something went wrong.",
        };
      }
      return { ok: false, unauthorized: false, error: "Network error — check your connection." };
    }
  }
}

/** Blob-returning sibling of adminFetch, for the CSV export routes
 * (GET .../export) -- those return a file body with Content-Disposition/
 * x-truncated headers, not JSON, so they need the raw axios response
 * rather than adminFetch's unwrapped `{ok, data}`. Used only by
 * useExport.ts's useCsvExport hook. Same silent-refresh behavior as
 * adminFetch. */
export async function adminFetchBlob(
  path: string,
): Promise<
  | { ok: true; blob: Blob; headers: Record<string, string> }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string }
> {
  let token = getAdminToken() ?? (await tryAdminRefresh());
  if (!token) return { ok: false, unauthorized: true };

  for (let attempt = 0; ; attempt++) {
    try {
      const res = await axios.request({
        method: "GET",
        url: `${API_BASE_URL}${path}`,
        headers: { Authorization: `Bearer ${token}` },
        responseType: "blob",
      });
      return {
        ok: true,
        blob: res.data,
        headers: res.headers as unknown as Record<string, string>,
      };
    } catch (err) {
      if (isAxiosError(err) && err.response) {
        if (err.response.status === 401) {
          clearAdminToken();
          const fresh = attempt === 0 ? await tryAdminRefresh() : null;
          if (fresh) {
            token = fresh;
            continue;
          }
          return { ok: false, unauthorized: true };
        }
        return {
          ok: false,
          unauthorized: false,
          error: await blobErrorToMessage(err.response.data),
        };
      }
      return { ok: false, unauthorized: false, error: "Network error — check your connection." };
    }
  }
}
