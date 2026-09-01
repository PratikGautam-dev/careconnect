"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getPortalHospital, getPortalToken, type PortalHospital } from "@/lib/portalAuth";
import { getStaffSession } from "@/lib/staffAuth";

/** Redirects to /portal/login if there's no stored token, otherwise returns
 * the cached hospital summary from login -- individual pages still handle
 * their own data fetch (and their own 401 handling via portalFetch) since
 * what they fetch differs per page.
 *
 * Doctor isolation fix (Spec.md Section 0's doctor-frontend-restoration
 * follow-up): a staff session with role="doctor" is redirected to their own
 * /doctor/dashboard instead of being allowed through -- every /portal/*
 * page this guard protects (appointments, patients, messages, ...) reads
 * through hospital-wide routes with no per-doctor filtering, so letting a
 * doctor session past this guard would show them every patient at the
 * hospital, not just their own. This is enforced HERE, once, rather than in
 * each of the eight pages that call usePortalGuard(). */
export function usePortalGuard() {
  const router = useRouter();
  const [hospital, setHospital] = useState<PortalHospital | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getPortalToken()) {
      router.push("/portal/login");
      return;
    }
    if (getStaffSession()?.role === "doctor") {
      router.push("/doctor/dashboard");
      return;
    }
    setHospital(getPortalHospital());
    setReady(true);
  }, [router]);

  return { hospital, ready };
}
