import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";

export type StatWithDelta = { value: number; delta: { value: string; direction: "up" | "down" } | null };

export type PharmacyDashboard = {
  stats: {
    prescriptions_today: StatWithDelta;
    medicines_dispensed_today: StatWithDelta;
    low_stock_items: StatWithDelta;
    near_expiry_items: StatWithDelta;
    pending_orders: StatWithDelta;
  };
  inventory_snapshot: { total_items: number; breakdown: { label: string; count: number }[] };
  low_stock: { id: number; name: string; quantity_on_hand: number; reorder_level: number }[];
  near_expiry: { id: number; medicine_name: string; batch_number: string; expiry_date: string; quantity_on_hand: number }[];
  top_selling_medicines: { medicine_id: number; name: string; units_dispensed: number }[];
  supplier_deliveries: { id: number; supplier_name: string; order_date: string; status: string }[];
  recent_activities: { type: string; message: string; at: string }[];
};

/** One combined fetch for the Pharmacy dashboard page -- matches
 * GET /api/portal/pharmacy/dashboard's own "one endpoint, not several"
 * shape (db/repositories/pharmacy_dashboard.py). */
export function usePharmacyDashboard(ready: boolean) {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ["portal-pharmacy-dashboard"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/pharmacy/dashboard");
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return result.data as PharmacyDashboard;
    },
  });

  return { dashboard: data ?? null, error: error instanceof Error ? error.message : null, isLoading, refetch };
}
