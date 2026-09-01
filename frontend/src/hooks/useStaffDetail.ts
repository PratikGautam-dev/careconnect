import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/adminAuth";

export type StaffDetail = {
  id: number;
  name: string;
  email: string;
  role: "admin" | "receptionist" | "doctor";
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
  const [staff, setStaff] = useState<StaffDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await adminFetch(`/api/admin/staff-users/${staffId}`);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    setStaff((result.data as { staff: StaffDetail }).staff);
  }, [staffId]);

  useEffect(() => {
    load();
  }, [load]);

  return { staff, error };
}
