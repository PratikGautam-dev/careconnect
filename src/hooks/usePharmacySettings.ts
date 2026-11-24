import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type PharmacySettingsData = {
  profile_branch_name: string | null;
  profile_contact_phone: string | null;
  profile_contact_email: string | null;
  profile_operating_hours: string | null;
  default_tax_percent: number;
  near_expiry_days: number;
  low_stock_alerts_enabled: boolean;
  print_show_logo: boolean;
  print_footer_text: string | null;
  print_format: string;
  sale_number_prefix: string;
  prescription_number_prefix: string;
  sales_return_number_prefix: string;
  purchase_return_number_prefix: string;
  adjustment_number_prefix: string;
  integration_emr_enabled: boolean;
  integration_billing_enabled: boolean;
  integration_finance_enabled: boolean;
  updated_at: string;
};

const QUERY_KEY = ["portal-pharmacy-settings"];

export function usePharmacySettings(ready: boolean) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/settings");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return result.data as PharmacySettingsData;
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (fields: Partial<PharmacySettingsData>) => {
      const result = await portalFetch("/api/portal/pharmacy/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return result.data as PharmacySettingsData;
    },
    onSuccess: (updated) => {
      toast.success("Settings saved");
      queryClient.setQueryData(QUERY_KEY, updated);
    },
    onError: (err) => toast.error("Couldn't save settings", err instanceof Error ? err.message : "Try again."),
  });

  return {
    settings: data,
    isLoading,
    updateSettings: (fields: Partial<PharmacySettingsData>) => updateMutation.mutateAsync(fields),
    saving: updateMutation.isPending,
  };
}

export type PharmacyCategory = { id: number; name: string };
export type PharmacyUnit = { id: number; name: string; kind: string };

export function usePharmacyCategories(ready: boolean) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-categories"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/settings/categories");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { categories: PharmacyCategory[] }).categories;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      const result = await portalFetch("/api/portal/pharmacy/settings/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-categories"] }),
    onError: (err) => toast.error("Couldn't add category", err instanceof Error ? err.message : "Try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/pharmacy/settings/categories/${id}/delete`, { method: "POST" });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-categories"] }),
    onError: (err) => toast.error("Couldn't remove category", err instanceof Error ? err.message : "Try again."),
  });

  return {
    categories: data ?? [],
    isLoading,
    createCategory: (name: string) => createMutation.mutateAsync(name),
    creating: createMutation.isPending,
    deleteCategory: (id: number) => deleteMutation.mutateAsync(id),
  };
}

export function usePharmacyUnits(ready: boolean) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-units"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/settings/units");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { units: PharmacyUnit[] }).units;
    },
  });

  const createMutation = useMutation({
    mutationFn: async ({ name, kind }: { name: string; kind: string }) => {
      const result = await portalFetch("/api/portal/pharmacy/settings/units", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, kind }),
      });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-units"] }),
    onError: (err) => toast.error("Couldn't add unit", err instanceof Error ? err.message : "Try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/pharmacy/settings/units/${id}/delete`, { method: "POST" });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-units"] }),
    onError: (err) => toast.error("Couldn't remove unit", err instanceof Error ? err.message : "Try again."),
  });

  return {
    units: data ?? [],
    isLoading,
    createUnit: (name: string, kind: string) => createMutation.mutateAsync({ name, kind }),
    creating: createMutation.isPending,
    deleteUnit: (id: number) => deleteMutation.mutateAsync(id),
  };
}
