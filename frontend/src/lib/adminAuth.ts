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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function adminFetch(path: string, init?: RequestInit): Promise<
  { ok: true; data: unknown } | { ok: false; unauthorized: true } | { ok: false; unauthorized: false; error: string }
> {
  const token = getAdminToken();
  if (!token) return { ok: false, unauthorized: true };

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    clearAdminToken();
    return { ok: false, unauthorized: true };
  }
  const data = await res.json();
  if (!res.ok) return { ok: false, unauthorized: false, error: data.error || (data.errors || []).join(" ") || "Something went wrong." };
  return { ok: true, data };
}
