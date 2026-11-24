import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Medicine = {
  id: number;
  name: string;
  generic_name: string | null;
  category: string | null;
  manufacturer: string | null;
  unit: string;
  unit_price: number | null;
  reorder_level: number;
  is_active: boolean;
  quantity_on_hand: number;
  nearest_expiry_date: string | null;
};

export type MedicineForm = {
  name: string;
  generic_name: string;
  category: string;
  manufacturer: string;
  unit: string;
  unit_price: string;
  reorder_level: string;
};

export type MedicineBatch = {
  id: number;
  medicine_id: number;
  batch_number: string;
  expiry_date: string;
  quantity_received: number;
  quantity_on_hand: number;
  cost_price: number | null;
};

export type MedicineFull = Medicine & { batches: MedicineBatch[] };

export async function fetchMedicine(id: number): Promise<MedicineFull | null> {
  const result = await portalFetch(`/api/portal/pharmacy/medicines/${id}`);
  if (!result.ok) return null;
  return (result.data as { medicine: MedicineFull }).medicine;
}

const QUERY_KEY = ["portal-pharmacy-medicines"];

export function useMedicines(ready: boolean) {
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/medicines");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { medicines: Medicine[] }).medicines;
    },
  });

  function toPayload(form: MedicineForm) {
    return {
      name: form.name.trim(),
      generic_name: form.generic_name.trim() || null,
      category: form.category.trim() || null,
      manufacturer: form.manufacturer.trim() || null,
      unit: form.unit.trim() || "unit",
      unit_price: form.unit_price ? Number(form.unit_price) : null,
      reorder_level: form.reorder_level ? Number(form.reorder_level) : 10,
    };
  }

  const createMutation = useMutation({
    mutationFn: async (form: MedicineForm) => {
      const result = await portalFetch("/api/portal/pharmacy/medicines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toPayload(form)),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { medicine: Medicine }).medicine;
    },
    onSuccess: () => {
      toast.success("Medicine added");
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => toast.error("Couldn't add medicine", err instanceof Error ? err.message : "Try again."),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, form }: { id: number; form: MedicineForm }) => {
      const result = await portalFetch(`/api/portal/pharmacy/medicines/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toPayload(form)),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Medicine updated");
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => toast.error("Couldn't update medicine", err instanceof Error ? err.message : "Try again."),
  });

  const setActiveMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const result = await portalFetch(`/api/portal/pharmacy/medicines/${id}/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active }),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
    onError: (err) => toast.error("Couldn't update medicine", err instanceof Error ? err.message : "Try again."),
  });

  return {
    medicines: data ?? [],
    error: error instanceof Error ? error.message : null,
    isLoading,
    createMedicine: (form: MedicineForm): Promise<Medicine> => createMutation.mutateAsync(form),
    creating: createMutation.isPending,
    updateMedicine: (id: number, form: MedicineForm) => updateMutation.mutateAsync({ id, form }),
    updating: updateMutation.isPending,
    setActive: (id: number, is_active: boolean) => setActiveMutation.mutate({ id, is_active }),
  };
}

export function emptyMedicineForm(): MedicineForm {
  return { name: "", generic_name: "", category: "", manufacturer: "", unit: "unit", unit_price: "", reorder_level: "10" };
}
