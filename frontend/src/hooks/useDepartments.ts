import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

export type Department = { id: string; name: string };

/** Lightweight departments-only fetch, reusing the same /api/portal/doctors
 * response the Doctors page already fetches from (its own department list
 * lives there -- there's no separate departments-only endpoint) and just
 * picking out `departments`, ignoring the doctors/on_leave_today_count it
 * also returns. Used by the Staff page/dialogs for a non-doctor staff
 * member's own department field. Left exactly as it was (this endpoint's
 * own `departments` list already includes every department, hidden/
 * inactive or not -- see doctors.py's portal_doctors()) -- untouched by
 * the fuller useDepartmentsAdmin() hook below, which is Settings ->
 * Departments' own real hook. */
export function useDepartments(ready: boolean) {
  const [departments, setDepartments] = useState<Department[] | null>(null);

  useEffect(() => {
    if (!ready) return;
    staffFetch("/api/portal/doctors").then((result) => {
      if (!result.ok) return;
      const data = result.data as { departments: Department[] };
      setDepartments(data.departments || []);
    });
  }, [ready]);

  return departments;
}

export type HeadOfDepartment = { id: string; name: string; qualification: string; phone: string; email: string | null };

export type DepartmentDetail = {
  id: string;
  name: string;
  floor_wing: string | null;
  consultation_hours: string | null;
  description: string | null;
  is_active: boolean;
  show_on_frontend: boolean;
  online_booking_enabled: boolean;
  whatsapp_booking_enabled: boolean;
  head_doctor: HeadOfDepartment | null;
  doctor_count: number;
  support_staff_count: number;
};

export type DepartmentFields = {
  name: string;
  floor_wing: string | null;
  consultation_hours: string | null;
  description: string | null;
  head_doctor_id: string | null;
};

export type DepartmentVisibility = {
  show_on_frontend: boolean;
  online_booking_enabled: boolean;
  whatsapp_booking_enabled: boolean;
};

/** Settings -> Departments tab's own real, full-featured hook -- separate
 * from useDepartments() above (which stays a thin per-dropdown list for
 * Staff dialogs) since this one needs the full profile/status/visibility
 * shape plus create/update/toggle mutations, backed by the dedicated
 * /api/portal/departments surface (portal/routes/departments.py). */
export function useDepartmentsAdmin(ready: boolean) {
  const router = useRouter();
  const [departments, setDepartments] = useState<DepartmentDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const result = await staffFetch("/api/portal/departments");
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    setError(null);
    const data = result.data as { departments: DepartmentDetail[] };
    setDepartments(data.departments);
  }, [router]);

  useEffect(() => {
    if (ready) reload();
  }, [ready, reload]);

  // Shared failure handling for every mutation below -- redirect on an
  // expired session (same as reload() above), otherwise surface the error
  // via toast, same pattern useAddStaff.ts/useEditStaff.ts already use.
  function handleFailure(result: { unauthorized: boolean; error?: string }, title: string): false {
    if (result.unauthorized) router.push("/portal/login");
    else toast.error(title, result.error);
    return false;
  }

  async function createDepartment(fields: DepartmentFields) {
    const result = await staffFetch("/api/portal/departments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!result.ok) return handleFailure(result, "Couldn't create department");
    await reload();
    toast.success("Department created", fields.name);
    return true;
  }

  async function updateDepartment(id: string, fields: DepartmentFields) {
    const result = await staffFetch(`/api/portal/departments/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!result.ok) return handleFailure(result, "Couldn't update department");
    await reload();
    toast.success("Department updated", fields.name);
    return true;
  }

  async function setDepartmentActive(id: string, isActive: boolean) {
    const result = await staffFetch(`/api/portal/departments/${id}/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    });
    if (!result.ok) return handleFailure(result, isActive ? "Couldn't activate department" : "Couldn't deactivate department");
    await reload();
    return true;
  }

  async function setDepartmentVisibility(id: string, visibility: DepartmentVisibility) {
    const result = await staffFetch(`/api/portal/departments/${id}/visibility`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(visibility),
    });
    if (!result.ok) return handleFailure(result, "Couldn't update patient-facing availability");
    await reload();
    return true;
  }

  return { departments, error, reload, createDepartment, updateDepartment, setDepartmentActive, setDepartmentVisibility };
}
