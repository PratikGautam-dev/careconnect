import { useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import type { NearExpiryBatch } from "@/hooks/usePharmacyInventory";

export function useNearExpiryBatches(ready: boolean, days?: number) {
  const { data, isLoading } = useQuery({
    queryKey: ["portal-pharmacy-near-expiry", days ?? "default"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const qs = days ? `?days=${days}` : "";
      const result = await portalFetch(`/api/portal/pharmacy/inventory/near-expiry${qs}`);
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { batches: NearExpiryBatch[] }).batches;
    },
  });
  return { nearExpiryBatches: data ?? [], isLoading };
}
