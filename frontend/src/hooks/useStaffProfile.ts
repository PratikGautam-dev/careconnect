import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { PortalHospital } from "@/lib/portalAuth";
import { staffFetch, type StaffRole } from "@/lib/staffAuth";

export type StaffProfile = { id: number; name: string; email: string; role: StaffRole; hospital: PortalHospital };

/** Profile settings page's own "who am I" -- StaffSession (localStorage)
 * has no email (login/refresh never returned it), so this hits the
 * dedicated GET /api/portal/staff/me instead of reading the cached session. */
export function useStaffProfile() {
  const router = useRouter();
  const [profile, setProfile] = useState<StaffProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await staffFetch("/api/portal/staff/me");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setProfile(result.data as StaffProfile);
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  return { profile, error };
}
