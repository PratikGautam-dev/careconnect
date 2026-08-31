// Section 15: Google OAuth user identity, kept deliberately separate from
// staffAuth.ts's staff session (its own dedicated "user_token" localStorage
// key, its own AUTH_SECRET-signed token on the backend). Only reached now
// for a Google identity with no staff_details row yet -- auth/google_oauth.py's
// callback issues a real staff session directly (bypassing this file
// entirely) for anyone who already has one, redirecting straight to the
// dashboard. This token only exists long enough to get through /api/auth/me
// and the onboarding wizard's own submission call.
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
