import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

export type StaffDetail = {
  id: number;
  name: string;
  email: string;
  role_id: number;
  role_name: string;
  is_doctor_role: boolean;
  hospital_id: number;
  hospital_name: string;
  is_active: boolean;
  created_at: string;
  doctor_name: string | null;
  specialization: string | null;
  qualification: string | null;
  years_experience: number | null;
  department_name: string | null;
};

/** Single-staff detail for /admin/users/[hospitalId]/[staffId]. */
export function useStaffDetail(staffId: number) {
  const { data, error } = useQuery({
    queryKey: ["admin-staff-detail", staffId],
    retry: false,
    queryFn: async () => {
      const result = await adminFetch(`/api/admin/staff-users/${staffId}`);
      return unwrapAdminResult<{ staff: StaffDetail }>(result).staff;
    },
  });

  return { staff: data ?? null, error: error ? (error as Error).message : null };
}
