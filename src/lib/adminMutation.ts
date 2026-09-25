export const SESSION_EXPIRED = "Session expired — refresh to sign in again.";

type AdminResult =
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

/** Shared unwrap for an adminFetch result inside a TanStack Query
 * queryFn/mutationFn. There's no standalone /admin/login route -- admin auth
 * is AdminSecretGate wrapping each page's content IN PLACE at the same URL
 * (src/components/admin/AdminSecretGate.tsx), and adminFetch() already
 * clears the (expired/invalid) token on a 401 before this ever runs. So
 * "redirect to login, then back to the current page" is just: reload the
 * current URL. AdminSecretGate's own mount-time check then finds no token,
 * shows its inline sign-in form at that same URL, and unlocks straight back
 * into the page the admin was already on once they sign in again -- no
 * redirect param needed, since the URL never changed. window.location.reload
 * (not router.refresh/push) because this file has no React context to call a
 * router hook from -- it's a plain function called from inside queryFn/
 * mutationFn, same reasoning adminFetch() below already applies. */
export function unwrapAdminResult<T>(result: AdminResult): T {
  if (!result.ok) {
    if (result.unauthorized && typeof window !== "undefined") {
      window.location.reload();
    }
    throw new Error(result.unauthorized ? SESSION_EXPIRED : result.error);
  }
  return result.data as T;
}
