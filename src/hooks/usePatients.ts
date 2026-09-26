import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";
import { useCursorPage, type CursorPageResult } from "@/hooks/useCursorPage";

export type Patient = {
  id: number;
  phone: string;
  name: string | null;
  patient_display_id: string | null;
  mrn: string | null;
  last_visit: string | null;
  visit_count: number;
  visited_count: number;
  date_of_birth: string | null;
  gender: string | null;
  age: number | null;
  status: "active" | "blocked" | "inactive";
  created_at: string;
  /** Department/doctor of this patient's most recent appointment (any
   * status) -- null for a patient who has never had one booked. */
  department_name: string | null;
  doctor_name: string | null;
  // Stamped once, at creation, when this patient matched another ACTIVE
  // patient on at least 3 of {name, phone, date_of_birth, gender} -- see
  // db/repositories/patients.py _flag_duplicate_if_matches(). Purely
  // informational (no merge/dismiss action yet); duplicate_flag_reason is
  // null exactly when duplicate_of_patient_id is.
  duplicate_of_patient_id: number | null;
  duplicate_flag_reason: string | null;
};

export type PatientsFilters = {
  search: string;
  department_name: string;
  status: string;
  gender: string;
};

export const EMPTY_PATIENTS_FILTERS: PatientsFilters = {
  search: "",
  department_name: "",
  status: "",
  gender: "",
};

type PatientsResponse = CursorPageResult<Patient> & {
  patients: Patient[];
  total_count: number;
  active_count: number;
  new_registrations_count: number;
};

export const PATIENTS_QUERY_KEY = "portal-patients";

/** Keyset-paginated (before_id/next_cursor/has_more): the portal's patients
 * list, row selection, and delete (single or bulk) for the /portal/patients
 * page. search/department_name/status/gender are all applied SERVER-SIDE
 * now (db.get_patients_page()) -- moved off the page's old client-side
 * filter (department/status/gender used to be applied to whatever page
 * happened to already be loaded), which silently broke once real
 * pagination replaced the old "fetch up to 200, filter in the browser"
 * shape -- a matching patient sitting on page 3 would never surface from a
 * page-1-only client filter. total/active/new-registration counts come
 * from the same response (db.get_patient_counts(), scoped by `search` only
 * -- see that function's own docstring for why), not len(this page). */
export function usePatients(ready: boolean, filters: PatientsFilters, pageSize: number) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<Patient[] | null>(null);

  const page = useCursorPage<PatientsFilters, PatientsResponse>(
    PATIENTS_QUERY_KEY,
    async (f, beforeId, limit) => {
      const params = new URLSearchParams();
      if (f.search) params.set("search", f.search);
      if (f.department_name) params.set("department_name", f.department_name);
      if (f.status) params.set("status", f.status);
      if (f.gender) params.set("gender", f.gender);
      if (beforeId !== null) params.set("before_id", String(beforeId));
      params.set("limit", String(limit));
      const result = await portalFetch(`/api/portal/patients?${params.toString()}`);
      return unwrapPortalResult<PatientsResponse>(router, result);
    },
    filters,
    pageSize,
    ready,
  );
  const patients = page.data?.patients;

  const deleteMutation = useMutation({
    mutationFn: async (patientIds: number[]) => {
      const result = await portalFetch("/api/portal/patients/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_ids: patientIds }),
      });
      return unwrapPortalResult<{ deleted: number[] }>(router, result);
    },
  });

  const toggleSelected = (id: number, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const toggleSelectAll = (checked: boolean) => {
    setSelected(checked ? new Set((patients ?? []).map((p) => p.id)) : new Set());
  };

  const runDelete = async (targets: Patient[]) => {
    setPendingDelete(null);
    try {
      const data = await deleteMutation.mutateAsync(targets.map((p) => p.id));
      const deletedIds = new Set(data.deleted);
      toast.success(
        deletedIds.size > 1 ? `${deletedIds.size} patients deleted` : "Patient deleted",
      );
      setSelected((prev) => {
        const next = new Set(prev);
        deletedIds.forEach((id) => next.delete(id));
        return next;
      });
      page.reload();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      toast.error("Couldn't delete patient" + (targets.length > 1 ? "s" : ""), message);
    }
  };

  const selectedPatients = (patients ?? []).filter((p) => selected.has(p.id));
  const allSelected = (patients?.length ?? 0) > 0 && selected.size === patients?.length;

  return {
    patients: patients ?? null,
    error: page.error,
    load: page.reload,
    hasNext: page.hasNext,
    hasPrev: page.hasPrev,
    pageNumber: page.pageNumber,
    goNext: page.goNext,
    goPrev: page.goPrev,
    selected,
    toggleSelected,
    toggleSelectAll,
    selectedPatients,
    allSelected,
    pendingDelete,
    setPendingDelete,
    deleting: deleteMutation.isPending,
    runDelete,
    stats: {
      total: page.data?.total_count ?? 0,
      active: page.data?.active_count ?? 0,
      newRegistrations: page.data?.new_registrations_count ?? 0,
    },
  };
}
