export const SESSION_EXPIRED = "Session expired — refresh to sign in again.";

type AdminResult =
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

/** Shared unwrap for an adminFetch result inside a TanStack Query
 * queryFn/mutationFn -- admin sessions don't auto-redirect on expiry (there's
 * no refresh-token flow here, unlike the portal's staffFetch), so this just
 * throws a message every caller can render as-is, no special
 * unauthorized-vs-error branching needed (contrast portalMutation.ts). */
export function unwrapAdminResult<T>(result: AdminResult): T {
  if (!result.ok) {
    throw new Error(result.unauthorized ? SESSION_EXPIRED : result.error);
  }
  return result.data as T;
}
