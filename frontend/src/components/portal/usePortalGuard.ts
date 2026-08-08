"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getPortalHospital, getPortalToken, type PortalHospital } from "@/lib/portalAuth";

/** Redirects to /portal/login if there's no stored token, otherwise returns
 * the cached hospital summary from login -- individual pages still handle
 * their own data fetch (and their own 401 handling via portalFetch) since
 * what they fetch differs per page. */
export function usePortalGuard() {
  const router = useRouter();
  const [hospital, setHospital] = useState<PortalHospital | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getPortalToken()) {
      router.push("/portal/login");
      return;
    }
    setHospital(getPortalHospital());
    setReady(true);
  }, [router]);

  return { hospital, ready };
}
