import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";
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
};

async function fetchPatients(search: string) {
  return portalFetch(`/api/portal/patients?search=${encodeURIComponent(search)}`);
}

async function deletePatients(patientIds: number[]) {
  return portalFetch("/api/portal/patients/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_ids: patientIds }),
  });
}

/** Loads + searches the portal's patients list, and owns row selection and
 * delete (single or bulk) for the /portal/patients page. */
export function usePatients(ready: boolean) {
  const router = useRouter();
  const [patients, setPatients] = useState<Patient[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<Patient[] | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(
    async (query: string) => {
      const result = await fetchPatients(query);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        else setError(result.error);
        return;
      }
      setPatients((result.data as { patients: Patient[] }).patients);
    },
    [router],
  );

  useEffect(() => {
    if (ready) load(search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, load]);

  useEffect(() => {
    if (!ready) return;
    const t = setTimeout(() => load(search), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

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
    setDeleting(true);
    const result = await deletePatients(targets.map((p) => p.id));
    setDeleting(false);
    setPendingDelete(null);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else {
        setError(result.error);
        toast.error("Couldn't delete patient" + (targets.length > 1 ? "s" : ""), result.error);
      }
      return;
    }
    const deletedIds = new Set((result.data as { deleted: number[] }).deleted);
    toast.success(deletedIds.size > 1 ? `${deletedIds.size} patients deleted` : "Patient deleted");
    setPatients((prev) => (prev ? prev.filter((p) => !deletedIds.has(p.id)) : prev));
    setSelected((prev) => {
      const next = new Set(prev);
      deletedIds.forEach((id) => next.delete(id));
      return next;
    });
  };

  const selectedPatients = (patients ?? []).filter((p) => selected.has(p.id));
  const allSelected = (patients?.length ?? 0) > 0 && selected.size === patients?.length;

  return {
    patients,
    error,
    search,
    setSearch,
    selected,
    toggleSelected,
    toggleSelectAll,
    selectedPatients,
    allSelected,
    pendingDelete,
    setPendingDelete,
    deleting,
    runDelete,
  };
}
