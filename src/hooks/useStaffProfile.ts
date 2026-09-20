import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { PortalHospital } from "@/lib/portalAuth";
import { staffFetch } from "@/lib/staffAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";

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

  const { data: profile, error: queryError } = useQuery({
    queryKey: ["portal-staff-profile"],
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/staff/me");
      return unwrapPortalResult<StaffProfile>(router, result);
    },
  });

  return {
    profile: profile ?? null,
    error: queryError ? "Couldn't load profile — try again." : null,
  };
}
