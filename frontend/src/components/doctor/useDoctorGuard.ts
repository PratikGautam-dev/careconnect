"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getStaffAccessToken, getStaffSession, type StaffSession } from "@/lib/staffAuth";

/** Redirects to /doctor/login if there's no staff session at all, and to
 * /portal/dashboard if the session exists but isn't a doctor -- so an
 * admin/receptionist landing on /doctor/* by mistake (a bookmark, a shared
 * link) gets routed back to their own portal instead of 401ing on every
 * /api/doctor/* call. Mirrors usePortalGuard.ts's role check in reverse. */
export function useDoctorGuard() {
  const router = useRouter();
  const [doctor, setDoctor] = useState<StaffSession | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getStaffAccessToken()) {
      router.push("/doctor/login");
      return;
    }
    const session = getStaffSession();
    if (!session?.is_doctor_role) {
      router.push("/portal/dashboard");
      return;
    }
    setDoctor(session);
    setReady(true);
  }, [router]);

  return { doctor, ready };
}
