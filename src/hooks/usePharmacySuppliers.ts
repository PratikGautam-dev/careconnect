import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type Supplier = {
  id: number;
  name: string;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  category: string | null;
  payment_terms: string | null;
  is_active: boolean;
};

export type SupplierForm = {
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  address: string;
  category: string;
  payment_terms: string;
};

export function emptySupplierForm(): SupplierForm {
  return { name: "", contact_person: "", phone: "", email: "", address: "", category: "", payment_terms: "" };
}

export const SUPPLIER_CATEGORIES = ["Medicines", "Consumables", "Surgical & Others", "Medical Devices", "Others"];
export const SUPPLIER_PAYMENT_TERMS = ["Net 30 Days", "Net 45 Days", "Net 60 Days", "Advance (100%)"];

const QUERY_KEY = ["portal-pharmacy-suppliers"];

export function usePharmacySuppliers(ready: boolean) {
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/suppliers");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { suppliers: Supplier[] }).suppliers;
    },
  });

  function toPayload(form: SupplierForm) {
    return {
      name: form.name.trim(),
      contact_person: form.contact_person.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      address: form.address.trim() || null,
      category: form.category.trim() || null,
      payment_terms: form.payment_terms.trim() || null,
    };
  }

  const createMutation = useMutation({
    mutationFn: async (form: SupplierForm) => {
      const result = await portalFetch("/api/portal/pharmacy/suppliers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toPayload(form)),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Supplier added");
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => toast.error("Couldn't add supplier", err instanceof Error ? err.message : "Try again."),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, form, is_active }: { id: number; form: SupplierForm; is_active: boolean }) => {
      const result = await portalFetch(`/api/portal/pharmacy/suppliers/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...toPayload(form), is_active }),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Supplier updated");
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => toast.error("Couldn't update supplier", err instanceof Error ? err.message : "Try again."),
  });

  return {
    suppliers: data ?? [],
    error: error instanceof Error ? error.message : null,
    isLoading,
    createSupplier: (form: SupplierForm) => createMutation.mutateAsync(form),
    creating: createMutation.isPending,
    updateSupplier: (id: number, form: SupplierForm, is_active: boolean) =>
      updateMutation.mutateAsync({ id, form, is_active }),
    updating: updateMutation.isPending,
  };
}

export type SupplierPerformance = {
  supplier_id: number;
  supplier_name: string;
  orders: number;
  otd_percent: number | null;
  fill_rate_percent: number | null;
};

export function useSupplierPerformance(ready: boolean) {
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-supplier-performance"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/suppliers/performance");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { performance: SupplierPerformance[] }).performance;
    },
  });
  return { performance: data ?? [], isLoading };
}

export function useSupplierPurchaseTotals(ready: boolean) {
  const { data } = useQuery({
    queryKey: ["portal-pharmacy-supplier-purchase-totals"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/suppliers/purchase-totals");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { totals: Record<string, number> }).totals;
    },
  });
  return { purchaseTotals: data ?? {} };
}
