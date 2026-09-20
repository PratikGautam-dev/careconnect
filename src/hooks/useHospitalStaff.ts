import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

export type StaffRow = {
  id: number;
  name: string;
  email: string;
  role_id: number;
  role_name: string;
  is_doctor_role: boolean;
  hospital_id: number;
  hospital_name: string;
  is_active: boolean;
};

/** Staff list for /admin/users/[hospitalId] -- scoped to one hospital, with
 * name/email search plus an active filter. Hospital name is fetched
 * independently of the (filterable) staff list, so the page header doesn't
 * disappear when a filter/search matches zero rows. No role filter --
 * dynamic-roles migration: roles are unbounded per hospital now, so a fixed
 * dropdown no longer makes sense here; the row's own role_name is still
 * shown per-person. Only `search` is debounced (300ms, same as
 * usePatients.ts's search box) -- hospitalId/activeFilter changes apply
 * immediately. */
export function useHospitalStaff(
  hospitalId: number,
  search: string,
  activeFilter: "" | "active" | "inactive",
) {
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const { data: hospitalName } = useQuery({
    queryKey: ["admin-hospital-name", hospitalId],
    retry: false,
    queryFn: async () => {
      const result = await adminFetch(`/api/admin/tenants/${hospitalId}`);
      return unwrapAdminResult<{ tenant: { name: string } }>(result).tenant.name;
    },
  });

  const {
    data: staff,
    error: queryError,
  } = useQuery({
    queryKey: ["admin-hospital-staff", hospitalId, activeFilter, debouncedSearch],
    retry: false,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("hospital_id", String(hospitalId));
      if (activeFilter) params.set("is_active", activeFilter === "active" ? "true" : "false");
      if (debouncedSearch) params.set("search", debouncedSearch);
      const result = await adminFetch(`/api/admin/staff-users?${params.toString()}`);
      return unwrapAdminResult<{ staff: StaffRow[] }>(result).staff;
    },
  });

  return {
    staff: staff ?? null,
    hospitalName: hospitalName ?? null,
    error: queryError ? (queryError as Error).message : null,
  };
}
