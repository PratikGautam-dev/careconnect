import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

export type RoleBreakdownEntry = { role_id: number; role_name: string; count: number };

export type HospitalStaffSummary = {
  id: number;
  name: string;
  is_active: boolean;
  data_tier: string;
  // Dynamic-roles migration: the old 3 fixed named counts (admin/doctor/
  // receptionist) don't generalize to a hospital's own admin-named roles --
  // full per-role breakdown instead.
  role_breakdown: RoleBreakdownEntry[];
  total_count: number;
};

/** Per-hospital staff headcounts for the /admin/users overview -- debounces
 * `search` (hospital name) the same 300ms as usePatients.ts's search box. */
export function useStaffSummary(search: string) {
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const { data, error } = useQuery({
    queryKey: ["admin-staff-summary", debouncedSearch],
    retry: false,
    queryFn: async () => {
      const params = new URLSearchParams();
      if (debouncedSearch) params.set("search", debouncedSearch);
      const result = await adminFetch(`/api/admin/staff-summary?${params.toString()}`);
      return unwrapAdminResult<{ hospitals: HospitalStaffSummary[] }>(result).hospitals;
    },
  });

  return { hospitals: data ?? null, error: error ? (error as Error).message : null };
}
