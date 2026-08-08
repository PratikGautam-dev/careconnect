const TOKEN_KEY = "portal_token";
const HOSPITAL_KEY = "portal_hospital";

export type PortalHospital = {
  id: number;
  name: string;
  data_tier: string;
  enabled_features: string[];
};

export function savePortalSession(token: string, hospital: PortalHospital) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(HOSPITAL_KEY, JSON.stringify(hospital));
}

export function getPortalToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getPortalHospital(): PortalHospital | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(HOSPITAL_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearPortalSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(HOSPITAL_KEY);
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** fetch() wrapper that attaches the portal Bearer token and treats a 401 as
 * a signal to clear the stale session -- callers redirect to /portal/login
 * on `unauthorized`, same as portal.py's own _current_hospital() returning
 * None sends the server-rendered version back to the login page. */
export async function portalFetch(path: string, init?: RequestInit): Promise<
  { ok: true; data: unknown } | { ok: false; unauthorized: true } | { ok: false; unauthorized: false; error: string }
> {
  const token = getPortalToken();
  if (!token) return { ok: false, unauthorized: true };

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    clearPortalSession();
    return { ok: false, unauthorized: true };
  }
  const data = await res.json();
  if (!res.ok) return { ok: false, unauthorized: false, error: data.error || "Something went wrong." };
  return { ok: true, data };
}
