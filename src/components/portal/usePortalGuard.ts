"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useStaffSession, useStaffSessionStatus } from "@/lib/staffAuth";

/** Redirects to /portal/login once the session status is confirmed
 * "unauthenticated" -- not on a synchronous token check, since the access
 * token lives only in memory (staffAuth.ts) and is legitimately empty on
 * every fresh page load even for an already-logged-in user, until
 * StaffSessionProvider's mount-time /me call (which silently retries via
 * the httpOnly refresh cookie when there's no in-memory token yet) has a
 * chance to resolve. Redirecting on an empty token synchronously would
 * bounce a genuinely logged-in user to the login page on every hard
 * refresh. `ready` mirrors that same "status === authenticated" gate, so
 * callers already using it to hold off their own data fetch (useDoctors(ready)
 * etc.) get this fix for free.
 *
 * A doctor session is allowed through like any other role -- every /portal/*
 * route is now RBAC-driven (portal/permissions.py) and the shared list/detail
 * endpoints scope themselves to the caller's own data when role=="doctor",
 * so there's no longer a reason to bounce doctors to a separate section. */
export function usePortalGuard() {
  const router = useRouter();
  const session = useStaffSession();
  const status = useStaffSessionStatus();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/portal/login");
    }
  }, [status, router]);

  return { hospital: session?.hospital ?? null, ready: status === "authenticated" };
}
