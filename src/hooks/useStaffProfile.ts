import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { PortalHospital } from "@/lib/portalAuth";
import { staffFetch } from "@/lib/staffAuth";

export type StaffProfile = {
  id: number;
  name: string;
  email: string;
  role_id: number;
  role_name: string;
  is_doctor_role: boolean;
  doctor_id: string | null;
  hospital: PortalHospital;
  employee_id: string;
  phone: string | null;
  address: string | null;
  department_id: string | null;
  department_name: string | null;
  reports_to_name: string | null;
  working_days: string[];
  working_hours: string[];
  breaks: string[];
  created_at: string;
  // Doctor-only -- null for every other role (Profile page's own "my
  // profile" query, get_own_profile(), sources these from the linked
  // doctors row).
  specialization: string | null;
  qualification: string | null;
  years_experience: number | null;
  location: string | null;
};

/** Profile page's own "who am I" -- StaffSession (localStorage)
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
