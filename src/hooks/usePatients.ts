import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

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

const NEW_REGISTRATION_WINDOW_DAYS = 7;

/** Loads + searches the portal's patients list, and owns row selection and
 * delete (single or bulk) for the /portal/patients page. Single page,
 * single consumer -- kept as one hook (like useEditTenant) rather than
 * separated into per-mutation hooks nothing else would import. `search` is
 * debounced 300ms before it hits the query key, same as before. */
export function usePatients(ready: boolean) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<Patient[] | null>(null);

  // Client-side filters on top of the already-loaded (search-scoped) list --
  // same "list is small, no extra round trip" reasoning as the Doctors page.
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [genderFilter, setGenderFilter] = useState("all");

  const [debouncedSearch, setDebouncedSearch] = useState(search);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const {
    data,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-patients", debouncedSearch],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(
        `/api/portal/patients?search=${encodeURIComponent(debouncedSearch)}`,
      );
      const patients = unwrapPortalResult<{ patients: Patient[] }>(router, result).patients;
      // Snapshotted here (inside the fetch, not Date.now() during render or
      // an effect -- both of which the newer react-hooks lint rules
      // disallow) -- close enough for the upcoming/past-style splits below
      // on a page that isn't left open for hours.
      return { patients, fetchedAt: Date.now() };
    },
  });
  const patients = data?.patients;

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
      toast.success(deletedIds.size > 1 ? `${deletedIds.size} patients deleted` : "Patient deleted");
      setSelected((prev) => {
        const next = new Set(prev);
        deletedIds.forEach((id) => next.delete(id));
        return next;
      });
      refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      toast.error("Couldn't delete patient" + (targets.length > 1 ? "s" : ""), message);
    }
  };

  const selectedPatients = (patients ?? []).filter((p) => selected.has(p.id));
  const allSelected = (patients?.length ?? 0) > 0 && selected.size === patients?.length;

  // Department options are scoped to departments this patient list has
  // actually had a visit in (derived from the real last-visit department on
  // each row) -- not the hospital's full department catalog, which isn't
  // fetched on this page.
  const departmentOptions = useMemo(() => {
    const names = new Set(
      (patients ?? []).map((p) => p.department_name).filter((n): n is string => !!n),
    );
    return [...names].sort();
  }, [patients]);

  const filteredPatients = useMemo(() => {
    return (patients ?? []).filter((p) => {
      if (departmentFilter !== "all" && p.department_name !== departmentFilter) return false;
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      if (genderFilter !== "all" && p.gender !== genderFilter) return false;
      return true;
    });
  }, [patients, departmentFilter, statusFilter, genderFilter]);

  const now = data?.fetchedAt ?? null;

  const stats = useMemo(() => {
    const list = patients ?? [];
    const cutoff = (now ?? 0) - NEW_REGISTRATION_WINDOW_DAYS * 24 * 60 * 60 * 1000;
    return {
      total: list.length,
      active: list.filter((p) => p.status === "active").length,
      newRegistrations:
        now === null
          ? 0
          : list.filter((p) => p.created_at && new Date(p.created_at).getTime() >= cutoff).length,
    };
  }, [patients, now]);

  return {
    patients: patients ?? null,
    error: queryError ? (queryError as Error).message : null,
    load: refetch,
    search,
    setSearch,
    selected,
    toggleSelected,
    toggleSelectAll,
    selectedPatients,
    allSelected,
    pendingDelete,
    setPendingDelete,
    deleting: deleteMutation.isPending,
    runDelete,
    departmentFilter,
    setDepartmentFilter,
    statusFilter,
    setStatusFilter,
    genderFilter,
    setGenderFilter,
    departmentOptions,
    filteredPatients,
    stats,
  };
}
