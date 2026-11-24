import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";
import type { Medicine } from "@/hooks/usePharmacyMedicines";

export type NearExpiryBatch = {
  id: number;
  medicine_id: number;
  medicine_name: string;
  batch_number: string;
  expiry_date: string;
  quantity_on_hand: number;
};

export type AddStockForm = {
  medicine_id: string;
  batch_number: string;
  expiry_date: string;
  quantity: string;
  cost_price: string;
  supplier_id: string;
};

export function emptyAddStockForm(): AddStockForm {
  return { medicine_id: "", batch_number: "", expiry_date: "", quantity: "", cost_price: "", supplier_id: "" };
}

const INVENTORY_KEY = ["portal-pharmacy-inventory"];

export function usePharmacyInventory(ready: boolean) {
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: INVENTORY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/inventory");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { inventory: Medicine[] }).inventory;
    },
  });

  const addStockMutation = useMutation({
    mutationFn: async (form: AddStockForm) => {
      const result = await portalFetch("/api/portal/pharmacy/inventory/add-stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          medicine_id: Number(form.medicine_id),
          batch_number: form.batch_number.trim(),
          expiry_date: form.expiry_date,
          quantity: Number(form.quantity),
          cost_price: form.cost_price ? Number(form.cost_price) : null,
          supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
        }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired." : (result.body?.errors as string[] | undefined)?.join(" ") || result.error,
        );
      }
    },
    onSuccess: () => {
      toast.success("Stock added");
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEY });
      queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-medicines"] });
      queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-dashboard"] });
    },
    onError: (err) => toast.error("Couldn't add stock", err instanceof Error ? err.message : "Try again."),
  });

  return {
    inventory: data ?? [],
    error: error instanceof Error ? error.message : null,
    isLoading,
    addStock: (form: AddStockForm) => addStockMutation.mutateAsync(form),
    addingStock: addStockMutation.isPending,
  };
}
