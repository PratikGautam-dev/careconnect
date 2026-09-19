"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getPortalToken } from "@/lib/portalAuth";
import { useStaffSession } from "@/lib/staffAuth";

/** Redirects to /portal/login if there's no stored token, otherwise returns
 * the hospital off StaffSessionContext (fetched fresh by StaffSessionProvider
 * -- see app/portal/layout.tsx -- not a localStorage cache) -- individual
 * pages still handle their own data fetch (and their own 401 handling via
 * portalFetch) since what they fetch differs per page.
 *
 * A doctor session is allowed through like any other role -- every /portal/*
 * route is now RBAC-driven (portal/permissions.py) and the shared list/detail
 * endpoints scope themselves to the caller's own data when role=="doctor",
 * so there's no longer a reason to bounce doctors to a separate section. */
export function usePortalGuard() {
  const router = useRouter();
  const session = useStaffSession();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getPortalToken()) {
      router.push("/portal/login");
      return;
    }
    setReady(true);
  }, [router]);

  return { hospital: session?.hospital ?? null, ready };
}
