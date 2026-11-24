import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type SaleType = "prescription" | "otc" | "ipd";

export type PharmacySale = {
  id: number;
  prescription_id: number | null;
  patient_id: number | null;
  patient_name: string | null;
  appointment_id: number | null;
  sale_number: string;
  sale_type: SaleType;
  subtotal_amount: number;
  tax_amount: number;
  total_amount: number;
  payment_status: "pending" | "paid" | "partially_paid" | "cancelled";
  payment_method: string | null;
  payment_amount: number | null;
  created_at: string;
};

export type NewOtcSalePayload = {
  sale_type: "otc" | "ipd";
  items: { medicine_id: number; quantity: number }[];
  patient_id?: number;
  appointment_id?: number;
};

export type PharmacySaleItem = {
  id: number;
  medicine_id: number;
  medicine_name: string;
  batch_number: string;
  quantity: number;
  unit_price: number;
  line_total: number;
};

export type PharmacySaleFull = PharmacySale & { items: PharmacySaleItem[] };

export function usePharmacyBilling(ready: boolean, paymentStatus?: string, page: number = 1, saleType?: SaleType) {
  const queryClient = useQueryClient();
  const queryKey = ["portal-pharmacy-billing-sales", paymentStatus ?? "all", saleType ?? "all", page];

  const { data, error, isLoading } = useQuery({
    queryKey,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), limit: "20" });
      if (paymentStatus) params.set("payment_status", paymentStatus);
      if (saleType) params.set("sale_type", saleType);
      const result = await portalFetch(`/api/portal/pharmacy-billing/sales?${params.toString()}`);
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return result.data as { sales: PharmacySale[]; total: number; page: number; limit: number };
    },
  });

  const createOtcSaleMutation = useMutation({
    mutationFn: async (payload: NewOtcSalePayload) => {
      const result = await portalFetch("/api/portal/pharmacy-billing/sales", {
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
      toast.success("Bill created");
      queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-billing-sales"] });
      queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-inventory"] });
      queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-medicines"] });
    },
    onError: (err) => toast.error("Couldn't create bill", err instanceof Error ? err.message : "Try again."),
  });

  const collectPaymentMutation = useMutation({
    mutationFn: async ({ id, payment_method, payment_amount }: { id: number; payment_method: string; payment_amount: number }) => {
      const result = await portalFetch(`/api/portal/pharmacy-billing/sales/${id}/collect-payment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payment_method, payment_amount }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired." : (result.body?.errors as string[] | undefined)?.join(" ") || result.error,
        );
      }
    },
    onSuccess: () => {
      toast.success("Payment collected");
      queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-billing-sales"] });
    },
    onError: (err) => toast.error("Couldn't collect payment", err instanceof Error ? err.message : "Try again."),
  });

  return {
    sales: data?.sales ?? [],
    total: data?.total ?? 0,
    error: error instanceof Error ? error.message : null,
    isLoading,
    collectPayment: (id: number, payment_method: string, payment_amount: number) =>
      collectPaymentMutation.mutateAsync({ id, payment_method, payment_amount }),
    collecting: collectPaymentMutation.isPending,
    createOtcSale: (payload: NewOtcSalePayload) => createOtcSaleMutation.mutateAsync(payload),
    creatingOtcSale: createOtcSaleMutation.isPending,
  };
}

export async function fetchPharmacySale(id: number): Promise<PharmacySaleFull | null> {
  const result = await portalFetch(`/api/portal/pharmacy-billing/sales/${id}`);
  if (!result.ok) return null;
  return (result.data as { sale: PharmacySaleFull }).sale;
}
