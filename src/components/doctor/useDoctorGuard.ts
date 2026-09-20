"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStaffSession, useStaffSessionStatus, type StaffSession } from "@/lib/staffAuth";

/** Redirects to /doctor/login if there's no staff session at all, and to
 * /portal/dashboard if the session exists but isn't a doctor -- so an
 * admin/receptionist landing on /doctor/* by mistake (a bookmark, a shared
 * link) gets routed back to their own portal instead of 401ing on every
 * /api/doctor/* call. Mirrors usePortalGuard.ts's role check in reverse.
 * Waits for `status` to resolve past "loading" before redirecting either
 * way -- same reasoning as usePortalGuard.ts's own guard, so a page reload
 * doesn't bounce a still-logged-in doctor before the session round trip
 * (which now includes a silent refresh via the httpOnly cookie) resolves. */
export function useDoctorGuard() {
  const router = useRouter();
  const session = useStaffSession();
  const status = useStaffSessionStatus();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/doctor/login");
      return;
    }
    if (status !== "authenticated") return;
    if (!session?.is_doctor_role) {
      router.push("/portal/dashboard");
      return;
    }
    setReady(true);
  }, [status, session, router]);

  return { doctor: session as StaffSession | null, ready };
}
