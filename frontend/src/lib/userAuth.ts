// Section 15: Google OAuth user identity, kept deliberately separate from
// portalAuth.ts's hospital-scoped session (its own dedicated
// "user_token"/"user" localStorage keys, its own AUTH_SECRET-signed token on
// the backend) -- this token only exists long enough to get through
// /api/auth/me and /api/auth/select-hospital right after signing in, not to
// be carried around the whole time someone is browsing a hospital's portal.
// Once a hospital is selected, savePortalSession() (portalAuth.ts) takes
// over and the rest of the app runs exactly as it did before this section.
const TOKEN_KEY = "user_token";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type AuthUser = { id: number; email: string; name: string | null };
export type OwnedHospital = { id: number; name: string };

export function saveUserSession(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getUserToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function clearUserSession() {
  localStorage.removeItem(TOKEN_KEY);
}

/** Google OAuth requires a real browser navigation (not fetch/XHR) -- the
 * backend redirects to Google and back, then hands control to
 * /auth/callback via its own redirect. One entry point used from both the
 * landing page CTA and /portal/login -- see user_auth.py's module docstring
 * for why sign-up and sign-in aren't two different flows here. */
export function googleLoginUrl(): string {
  return `${API_BASE_URL}/auth/google/login`;
}

export async function fetchAuthMe(): Promise<
  { user: AuthUser; owned_hospitals: OwnedHospital[] } | null
> {
  const token = getUserToken();
  if (!token) return null;
  const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    clearUserSession();
    return null;
  }
  return res.json();
}

/** Exchanges the user session for the existing hospital-scoped portal
 * session token (portal.py's _sign_session) -- ownership is re-checked
 * server-side, never trusted from this call alone. */
export async function selectHospital(hospitalId: number): Promise<
  {
    token: string;
    expires_at: number;
    hospital: {
      id: number;
      name: string;
      data_tier: string;
      enabled_features: string[];
      tenant_type: string;
      admin_capabilities: string[];
    };
  } | null
> {
  const token = getUserToken();
  if (!token) return null;
  const res = await fetch(`${API_BASE_URL}/api/auth/select-hospital`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ hospital_id: hospitalId }),
  });
  if (!res.ok) return null;
  return res.json();
}
