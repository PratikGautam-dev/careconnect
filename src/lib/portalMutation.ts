import { useRouter } from "next/navigation";

export const UNAUTHORIZED_ERROR = "__portal_unauthorized__";

type PortalResult =
  | { ok: true; data: unknown }
  | { ok: false; unauthorized: true }
  | { ok: false; unauthorized: false; error: string };

/** Shared unwrap for a portalFetch/staffFetch result inside a TanStack Query
 * queryFn/mutationFn -- redirects to login on an expired session (same as
 * every hand-rolled hook already did) and throws either UNAUTHORIZED_ERROR
 * (silent, since the redirect already happened) or the server's own error
 * message, so a caller's onError only needs isPortalMutationError() before
 * toasting instead of re-deriving this branch every time. */
export function unwrapPortalResult<T>(
  router: ReturnType<typeof useRouter>,
  result: PortalResult,
): T {
  if (!result.ok) {
    if (result.unauthorized) {
      router.push("/portal/login");
      throw new Error(UNAUTHORIZED_ERROR);
    }
    throw new Error(result.error);
  }
  return result.data as T;
}

/** True for a real, toast-worthy failure -- false for the silent
 * "session expired, already redirecting" case. */
export function isPortalMutationError(error: unknown): error is Error {
  return error instanceof Error && error.message !== UNAUTHORIZED_ERROR;
}
