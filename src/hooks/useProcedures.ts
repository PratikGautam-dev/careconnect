import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export const PROCEDURE_CATEGORIES = [
  { value: "chemotherapy", label: "Chemotherapy" },
  { value: "dialysis", label: "Dialysis" },
  { value: "infusion_therapy", label: "Infusion Therapy" },
  { value: "dressing_wound_care", label: "Dressing / Wound Care" },
  { value: "injection", label: "Injection" },
  { value: "minor_procedure", label: "Minor Procedure" },
  { value: "other", label: "Other" },
] as const;

export const PROCEDURE_BOOKING_MODES = [
  { value: "instant", label: "Instant" },
  { value: "approval_required", label: "Approval Required" },
] as const;

export type Procedure = {
  id: number;
  category: string;
  name: string;
  department_id: string | null;
  booking_mode: "instant" | "approval_required";
  duration_minutes: number;
  estimated_price_min: number | null;
  estimated_price_max: number | null;
  is_active: boolean;
  sort_order: number;
};

export type ProcedureFields = {
  category: string;
  name: string;
  booking_mode: "instant" | "approval_required";
  duration_minutes: number;
  department_id: string | null;
  estimated_price_min: number | null;
  estimated_price_max: number | null;
};

/** Settings -> Procedures tab's own hook -- same list+dialog shape as
 * useDepartments.ts's useDepartmentsAdmin(), backed by
 * portal/routes/procedures.py's dedicated /api/portal/procedures CRUD
 * (POST/PUT, price fields included) that had no admin UI calling it before
 * this tab. */
export function useProceduresAdmin(ready: boolean) {
  const router = useRouter();

  const {
    data: procedures,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-procedures-admin"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/procedures");
      return unwrapPortalResult<{ procedures: Procedure[] }>(router, result).procedures;
    },
  });
  const error = queryError ? "Couldn't load procedures — try again." : null;
  const reload = refetch;

  // Shared failure handling for every mutation below -- redirect on an
  // expired session (same as reload() above), otherwise surface the error
  // via toast, same pattern useDepartmentsAdmin's own mutations use.
  function handleFailure(result: { unauthorized: boolean; error?: string }, title: string): false {
    if (result.unauthorized) router.push("/portal/login");
    else toast.error(title, result.error);
    return false;
  }

  async function createProcedure(fields: ProcedureFields) {
    const result = await portalFetch("/api/portal/procedures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!result.ok) return handleFailure(result, "Couldn't create procedure");
    await reload();
    toast.success("Procedure created", fields.name);
    return true;
  }

  async function updateProcedure(id: number, fields: ProcedureFields) {
    const result = await portalFetch(`/api/portal/procedures/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!result.ok) return handleFailure(result, "Couldn't update procedure");
    await reload();
    toast.success("Procedure updated", fields.name);
    return true;
  }

  async function setProcedureActive(id: number, isActive: boolean) {
    const result = await portalFetch(`/api/portal/procedures/${id}/active`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    });
    if (!result.ok)
      return handleFailure(
        result,
        isActive ? "Couldn't activate procedure" : "Couldn't deactivate procedure",
      );
    await reload();
    return true;
  }

  return {
    procedures: procedures ?? null,
    error,
    reload,
    createProcedure,
    updateProcedure,
    setProcedureActive,
  };
}
