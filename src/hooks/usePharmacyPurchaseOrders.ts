import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type PurchaseOrder = {
  id: number;
  supplier_id: number;
  supplier_name: string;
  status: "pending" | "in_transit" | "delivered" | "delayed" | "cancelled";
  order_date: string;
  expected_delivery_date: string | null;
  delivered_at: string | null;
  total_amount: number | null;
  notes: string | null;
};

export type PurchaseOrderItem = { id: number; medicine_id: number; medicine_name: string; quantity_ordered: number; quantity_received: number; unit_cost: number | null };
export type PurchaseOrderFull = PurchaseOrder & { items: PurchaseOrderItem[] };

export type NewPurchaseOrderItem = { medicine_id: number; quantity_ordered: number; unit_cost: number | null };

const QUERY_KEY = ["portal-pharmacy-purchase-orders"];

export function usePharmacyPurchaseOrders(ready: boolean) {
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/purchase-orders");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { purchase_orders: PurchaseOrder[] }).purchase_orders;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: { supplier_id: number; order_date: string; items: NewPurchaseOrderItem[]; notes?: string }) => {
      const result = await portalFetch("/api/portal/pharmacy/purchase-orders", {
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
      toast.success("Purchase order created");
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => toast.error("Couldn't create purchase order", err instanceof Error ? err.message : "Try again."),
  });

  return {
    purchaseOrders: data ?? [],
    error: error instanceof Error ? error.message : null,
    isLoading,
    createPurchaseOrder: (payload: { supplier_id: number; order_date: string; items: NewPurchaseOrderItem[]; notes?: string }) =>
      createMutation.mutateAsync(payload),
    creating: createMutation.isPending,
  };
}

export async function fetchPurchaseOrder(id: number): Promise<PurchaseOrderFull | null> {
  const result = await portalFetch(`/api/portal/pharmacy/purchase-orders/${id}`);
  if (!result.ok) return null;
  return (result.data as { purchase_order: PurchaseOrderFull }).purchase_order;
}

export async function receivePurchaseOrderDelivery(
  id: number, itemBatches: { purchase_order_item_id: number; batch_number: string; expiry_date: string; quantity_received: number }[],
): Promise<{ ok: true; purchaseOrder: PurchaseOrderFull } | { ok: false; error: string }> {
  const result = await portalFetch(`/api/portal/pharmacy/purchase-orders/${id}/receive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_batches: itemBatches }),
  });
  if (!result.ok) {
    return { ok: false, error: result.unauthorized ? "Session expired." : result.error };
  }
  return { ok: true, purchaseOrder: (result.data as { purchase_order: PurchaseOrderFull }).purchase_order };
}

export function useRecentReceipts(ready: boolean) {
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-recent-receipts"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/purchase-orders/recent-receipts");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { receipts: PurchaseOrder[] }).receipts;
    },
  });
  return { recentReceipts: data ?? [], isLoading };
}
