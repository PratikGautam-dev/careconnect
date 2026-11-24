import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";

export type PharmacyReports = {
  total_sales: number;
  prescriptions_dispensed: number;
  items_sold: number;
  inventory_value: number;
  sales_trend: { date: string; amount: number }[];
  sales_by_category: { label: string; count: number }[];
  top_selling_medicines: { medicine_id: number; medicine_name: string; items_sold: number; sales_amount: number }[];
  stock_movement: { stock_in: number; stock_out: number; net_movement: number; low_stock_items: number };
  procurement_summary: {
    id: number; supplier_name: string | null; order_date: string; status: string; total_amount: number | null;
  }[];
};

export function usePharmacyReports(ready: boolean, days: number = 30) {
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-reports", days],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/pharmacy/reports?days=${days}`);
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return result.data as PharmacyReports;
    },
  });
  return { reports: data, isLoading };
}
