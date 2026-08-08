// Platform-admin (tenant list/edit) auth -- deliberately separate from
// lib/portalAuth.ts's hospital-staff session. Uses TENANTS_ADMIN_SECRET, a
// different credential from the onboarding wizard's ADMIN_SECRET, so a
// leaked onboarding secret can't also expose every existing tenant's data.
// Stored in sessionStorage (not localStorage): this is a raw shared secret,
// not a scoped signed token, so it's deliberately given the shorter
// lifetime/exposure of a single tab session.

const SECRET_KEY = "admin_tenants_secret";

export function getAdminSecret(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(SECRET_KEY);
}

export function setAdminSecret(secret: string) {
  sessionStorage.setItem(SECRET_KEY, secret);
}

export function clearAdminSecret() {
  sessionStorage.removeItem(SECRET_KEY);
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function adminFetch(path: string, init?: RequestInit): Promise<
  { ok: true; data: unknown } | { ok: false; unauthorized: true } | { ok: false; unauthorized: false; error: string }
> {
  const secret = getAdminSecret();
  if (!secret) return { ok: false, unauthorized: true };

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...(init?.headers || {}), "X-Admin-Secret": secret },
  });

  if (res.status === 401) {
    clearAdminSecret();
    return { ok: false, unauthorized: true };
  }
  const data = await res.json();
  if (!res.ok) return { ok: false, unauthorized: false, error: data.error || (data.errors || []).join(" ") || "Something went wrong." };
  return { ok: true, data };
}
