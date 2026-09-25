import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { toast } from "@/lib/toast";

export type Plan = {
  id: number;
  name: string;
  description: string | null;
  price_monthly: number;
  annual_discount_pct: number;
  // admin_capabilities keys (portal/capabilities.py) -- a plan's "features"
  // ARE the hospital's real staff-portal menu access, not marketing text.
  // See src/lib/hospitalCapabilities.ts for labels/icons for these keys.
  capabilities: string[];
  max_users: number | null; // null = unlimited
  max_bookings: number | null; // null = unlimited, per subscription period
  is_active: boolean;
  is_popular: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type PlanWritePayload = {
  name: string;
  description: string | null;
  price_monthly: number;
  annual_discount_pct: number;
  capabilities: string[];
  max_users: number | null;
  max_bookings: number | null;
  is_active: boolean;
  is_popular: boolean;
  sort_order: number;
};

const PLANS_QUERY_KEY = ["admin-plans"] as const;

/** CRUD for the CareConnect pricing-tier catalog (admin/plans_api.py) --
 * backs /admin/plans-billing's plan cards, replacing what used to be a
 * hardcoded PLANS array. `allCapabilities` is the same admin_capabilities
 * vocabulary Access Control uses, returned alongside the list so the
 * create/edit dialog's feature picker doesn't need a second request. */
export function useAdminPlans() {
  const queryClient = useQueryClient();

  const { data, error, refetch } = useQuery({
    queryKey: PLANS_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/plans");
      return unwrapAdminResult<{ plans: Plan[]; all_capabilities: string[] }>(result);
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: PlanWritePayload) => {
      const result = await adminFetch("/api/admin/plans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<{ plan?: Plan; errors?: string[] }>(result);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: number;
      payload: Partial<PlanWritePayload> & Record<string, unknown>;
    }) => {
      const result = await adminFetch(`/api/admin/plans/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<{ plan?: Plan; errors?: string[] }>(result);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await adminFetch(`/api/admin/plans/${id}`, { method: "DELETE" });
      return unwrapAdminResult<{ status?: string }>(result);
    },
  });

  async function createPlan(payload: PlanWritePayload): Promise<boolean> {
    try {
      const data = await createMutation.mutateAsync(payload);
      if (data.errors?.length) {
        toast.error("Couldn't create plan", data.errors[0]);
        return false;
      }
      toast.success(`${payload.name} created`);
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't create plan",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  // description/max_users are nullable-clearable fields -- the backend
  // distinguishes "leave alone" from "clear it" via *_set sentinel flags
  // (admin/plans_api.py's PlanUpdatePayload), set here whenever the caller
  // includes either key at all, matching how the edit dialog always sends
  // the full form.
  async function updatePlan(id: number, payload: Partial<PlanWritePayload>): Promise<boolean> {
    const body: Record<string, unknown> = { ...payload };
    if ("description" in payload) body.description_set = true;
    if ("max_users" in payload) body.max_users_set = true;
    if ("max_bookings" in payload) body.max_bookings_set = true;
    try {
      const data = await updateMutation.mutateAsync({ id, payload: body });
      if (data.errors?.length) {
        toast.error("Couldn't save plan", data.errors[0]);
        return false;
      }
      toast.success("Plan saved");
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't save plan",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  async function toggleActive(plan: Plan): Promise<boolean> {
    const ok = await updatePlan(plan.id, { is_active: !plan.is_active });
    if (ok) toast.success(plan.is_active ? `${plan.name} turned off` : `${plan.name} turned on`);
    return ok;
  }

  async function deletePlan(id: number, name: string): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(id);
      toast.success(`${name} deleted`);
      queryClient.setQueryData(
        PLANS_QUERY_KEY,
        (prev: { plans: Plan[]; all_capabilities: string[] } | undefined) =>
          prev ? { ...prev, plans: prev.plans.filter((p) => p.id !== id) } : prev,
      );
      return true;
    } catch (err) {
      // 409 "N hospital(s) are on this plan..." lands here as a plain Error
      // message (unwrapAdminResult) -- surfaced as-is, it's already written
      // for an operator to read.
      toast.error(
        "Couldn't delete plan",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  return {
    plans: data?.plans ?? null,
    allCapabilities: data?.all_capabilities ?? [],
    error: error ? (error as Error).message : null,
    createPlan,
    updatePlan,
    toggleActive,
    deletePlan,
    creating: createMutation.isPending,
    updating: updateMutation.isPending,
    deleting: deleteMutation.isPending,
  };
}
