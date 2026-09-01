import { useCallback, useEffect, useState } from "react";
import { adminFetch } from "@/lib/adminAuth";

export type StaffRow = {
  id: number;
  name: string;
  email: string;
  role: "admin" | "receptionist" | "doctor";
  hospital_id: number;
  hospital_name: string;
  is_active: boolean;
};

/** Staff list for /admin/users/[hospitalId] -- scoped to one hospital, with
 * name/email search plus role/active filters. Hospital name is fetched
 * independently of the (filterable) staff list, so the page header doesn't
 * disappear when a filter/search matches zero rows. */
export function useHospitalStaff(
  hospitalId: number,
  search: string,
  roleFilter: "" | "admin" | "receptionist" | "doctor",
  activeFilter: "" | "active" | "inactive",
) {
  const [staff, setStaff] = useState<StaffRow[] | null>(null);
  const [hospitalName, setHospitalName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminFetch(`/api/admin/tenants/${hospitalId}`).then((result) => {
      if (result.ok) setHospitalName((result.data as { tenant: { name: string } }).tenant.name);
    });
  }, [hospitalId]);

  const load = useCallback(
    async (query: string) => {
      const params = new URLSearchParams();
      params.set("hospital_id", String(hospitalId));
      if (roleFilter) params.set("role", roleFilter);
      if (activeFilter) params.set("is_active", activeFilter === "active" ? "true" : "false");
      if (query) params.set("search", query);
      const result = await adminFetch(`/api/admin/staff-users?${params.toString()}`);
      if (!result.ok) {
        setError(result.unauthorized ? "Session expired — refresh to sign in again." : result.error);
        return;
      }
      setStaff((result.data as { staff: StaffRow[] }).staff);
    },
    [hospitalId, roleFilter, activeFilter],
  );

  useEffect(() => {
    load(search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    const t = setTimeout(() => load(search), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  return { staff, hospitalName, error };
}
