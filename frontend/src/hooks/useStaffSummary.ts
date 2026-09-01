import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/adminAuth";

export type HospitalStaffSummary = {
  id: number;
  name: string;
  is_active: boolean;
  data_tier: string;
  admin_count: number;
  doctor_count: number;
  receptionist_count: number;
  total_count: number;
};

/** Per-hospital staff headcounts for the /admin/users overview -- debounces
 * `search` (hospital name) the same 300ms as usePatients.ts's search box. */
export function useStaffSummary(search: string) {
  const [hospitals, setHospitals] = useState<HospitalStaffSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (query: string) => {
    const params = new URLSearchParams();
    if (query) params.set("search", query);
    const result = await adminFetch(`/api/admin/staff-summary?${params.toString()}`);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
      return;
    }
    setHospitals((result.data as { hospitals: HospitalStaffSummary[] }).hospitals);
  }, []);

  useEffect(() => {
    load(search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    const t = setTimeout(() => load(search), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  return { hospitals, error };
}
