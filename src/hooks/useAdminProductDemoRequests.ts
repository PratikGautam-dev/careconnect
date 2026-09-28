import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { toast } from "@/lib/toast";

export type DemoRequestStatus = "new" | "contacted" | "scheduled" | "closed";

export type ProductDemoRequestRow = {
  id: number;
  request_number: string;
  name: string;
  email: string;
  phone: string | null;
  hospital_name: string | null;
  message: string | null;
  status: DemoRequestStatus;
  created_at: string;
  updated_at: string;
};

export type ProductDemoRequestSummary = {
  total: number;
  new: number;
  contacted: number;
  scheduled: number;
  closed: number;
};

const REQUESTS_QUERY_KEY = ["admin-product-demo-requests"] as const;

/** Mirrors useAdminSupportTickets.ts's own shape exactly -- the Product
 * Demo Requests page is the same "cross-tenant lead queue reviewed only by
 * the platform super admin" pattern, just for public/product_demo_requests_api.py's
 * unauthenticated landing-page submissions instead of staff-raised tickets. */
export function useAdminProductDemoRequests() {
  const queryClient = useQueryClient();

  const { data, error, refetch } = useQuery({
    queryKey: REQUESTS_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/product-demo-requests");
      return unwrapAdminResult<{ requests: ProductDemoRequestRow[]; summary: ProductDemoRequestSummary }>(
        result,
      );
    },
  });

  const statusMutation = useMutation({
    mutationFn: async ({ requestId, status }: { requestId: number; status: DemoRequestStatus }) => {
      const result = await adminFetch(`/api/admin/product-demo-requests/${requestId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      return unwrapAdminResult<{ request: ProductDemoRequestRow }>(result);
    },
  });

  async function setStatus(requestId: number, status: DemoRequestStatus): Promise<boolean> {
    try {
      const { request } = await statusMutation.mutateAsync({ requestId, status });
      queryClient.setQueryData(
        REQUESTS_QUERY_KEY,
        (
          prev: { requests: ProductDemoRequestRow[]; summary: ProductDemoRequestSummary } | undefined,
        ) =>
          prev
            ? { ...prev, requests: prev.requests.map((r) => (r.id === requestId ? request : r)) }
            : prev,
      );
      toast.success("Request status updated");
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't update request status",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  return {
    requests: data?.requests ?? null,
    summary: data?.summary ?? null,
    error: error ? (error as Error).message : null,
    setStatus,
    updatingStatus: statusMutation.isPending,
    load: refetch,
  };
}
