import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type ReturnStatus = "pending" | "completed" | "cancelled";

export type SalesReturn = {
  id: number;
  type: "sales_return";
  return_number: string;
  pharmacy_sale_id: number | null;
  prescription_id: number | null;
  patient_id: number | null;
  reference_label: string;
  party_label: string;
  reason: string;
  amount: number;
  status: ReturnStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type PurchaseReturn = {
  id: number;
  type: "purchase_return";
  return_number: string;
  supplier_id: number;
  purchase_order_id: number | null;
  reference_label: string;
  party_label: string;
  reason: string;
  amount: number;
  status: ReturnStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type StockAdjustment = {
  id: number;
  type: "stock_adjustment";
  return_number: string;
  medicine_id: number;
  medicine_batch_id: number | null;
  reference_label: string;
  party_label: string;
  adjustment_type: string;
  quantity_delta: number;
  reason: string | null;
  amount: number;
  status: ReturnStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ReturnsSummary = {
  sales_returns_count: number;
  purchase_returns_count: number;
  pending_adjustments_count: number;
  adjustment_value: number;
  total_returns: number;
  total_adjustments: number;
  total_returns_value: number;
  total_adjustments_value: number;
  net_adjustment_value: number;
  return_reasons: { label: string; count: number }[];
};

export type NewSalesReturnPayload = {
  reason: string;
  items: { medicine_id: number; quantity: number; unit_price: number; medicine_batch_id?: number }[];
  pharmacy_sale_id?: number;
  prescription_id?: number;
  patient_id?: number;
  notes?: string;
};

export type NewPurchaseReturnPayload = {
  supplier_id: number;
  reason: string;
  items: { medicine_id: number; quantity: number; unit_cost: number; medicine_batch_id: number }[];
  purchase_order_id?: number;
  notes?: string;
};

export type NewStockAdjustmentPayload = {
  medicine_id: number;
  adjustment_type: string;
  quantity_delta: number;
  medicine_batch_id?: number;
  reason?: string;
  notes?: string;
};

function invalidateAll(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-returns"] });
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-inventory"] });
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-medicines"] });
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-dashboard"] });
}

export function useReturnsSummary(ready: boolean) {
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-returns", "summary"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/returns/summary");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return result.data as ReturnsSummary;
    },
  });
  return { summary: data, isLoading };
}

export function useSalesReturns(ready: boolean) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-returns", "sales"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/returns/sales");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { returns: SalesReturn[] }).returns;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: NewSalesReturnPayload) => {
      const result = await portalFetch("/api/portal/pharmacy/returns/sales", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired." : (result.body?.errors as string[] | undefined)?.join(" ") || result.error,
        );
      }
    },
    onSuccess: () => {
      toast.success("Sales return recorded");
      invalidateAll(queryClient);
    },
    onError: (err) => toast.error("Couldn't record return", err instanceof Error ? err.message : "Try again."),
  });

  const cancelMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/pharmacy/returns/sales/${id}/cancel`, { method: "POST" });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Return cancelled");
      invalidateAll(queryClient);
    },
    onError: (err) => toast.error("Couldn't cancel return", err instanceof Error ? err.message : "Try again."),
  });

  return {
    returns: data ?? [],
    isLoading,
    createReturn: (payload: NewSalesReturnPayload) => createMutation.mutateAsync(payload),
    creating: createMutation.isPending,
    cancelReturn: (id: number) => cancelMutation.mutateAsync(id),
  };
}

export function usePurchaseReturns(ready: boolean) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-returns", "purchase"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/returns/purchase");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { returns: PurchaseReturn[] }).returns;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: NewPurchaseReturnPayload) => {
      const result = await portalFetch("/api/portal/pharmacy/returns/purchase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired." : (result.body?.errors as string[] | undefined)?.join(" ") || result.error,
        );
      }
    },
    onSuccess: () => {
      toast.success("Purchase return recorded");
      invalidateAll(queryClient);
    },
    onError: (err) => toast.error("Couldn't record return", err instanceof Error ? err.message : "Try again."),
  });

  const cancelMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/pharmacy/returns/purchase/${id}/cancel`, { method: "POST" });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Return cancelled");
      invalidateAll(queryClient);
    },
    onError: (err) => toast.error("Couldn't cancel return", err instanceof Error ? err.message : "Try again."),
  });

  return {
    returns: data ?? [],
    isLoading,
    createReturn: (payload: NewPurchaseReturnPayload) => createMutation.mutateAsync(payload),
    creating: createMutation.isPending,
    cancelReturn: (id: number) => cancelMutation.mutateAsync(id),
  };
}

export function useStockAdjustments(ready: boolean) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-returns", "adjustments"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/returns/adjustments");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { adjustments: StockAdjustment[] }).adjustments;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: NewStockAdjustmentPayload) => {
      const result = await portalFetch("/api/portal/pharmacy/returns/adjustments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired." : (result.body?.errors as string[] | undefined)?.join(" ") || result.error,
        );
      }
    },
    onSuccess: () => {
      toast.success("Stock adjustment recorded");
      invalidateAll(queryClient);
    },
    onError: (err) => toast.error("Couldn't record adjustment", err instanceof Error ? err.message : "Try again."),
  });

  const cancelMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/pharmacy/returns/adjustments/${id}/cancel`, { method: "POST" });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Adjustment cancelled");
      invalidateAll(queryClient);
    },
    onError: (err) => toast.error("Couldn't cancel adjustment", err instanceof Error ? err.message : "Try again."),
  });

  return {
    adjustments: data ?? [],
    isLoading,
    createAdjustment: (payload: NewStockAdjustmentPayload) => createMutation.mutateAsync(payload),
    creating: createMutation.isPending,
    cancelAdjustment: (id: number) => cancelMutation.mutateAsync(id),
  };
}
