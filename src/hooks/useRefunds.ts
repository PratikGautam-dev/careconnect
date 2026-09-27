import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export type RefundStatus =
  "pending_approval" | "approved" | "processing" | "completed" | "failed" | "rejected";

// Matches db/repositories/refunds.py's _refund_request_to_dict() -- one row
// per cancellation that had money to give back (a plain cancel with no
// refund due creates no row at all).
export type RefundRequest = {
  id: number;
  hospital_id: number;
  appointment_id: number;
  payment_id: number;
  cancelled_by: "patient" | "hospital";
  reason: string | null;
  base_amount: number;
  deduction_percent: number;
  deduction_amount: number;
  gst_amount: number;
  platform_fee_amount: number;
  refund_amount: number;
  status: RefundStatus;
  approved_by_identity_id: number | null;
  approved_at: string | null;
  razorpay_refund_id: string | null;
  razorpay_refund_status: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string | null;
  processed_at: string | null;
  // Denormalized off the cancelled appointment (list_refund_requests()'s
  // own join) -- not present on a single-row mutation response (approve/
  // reject/sync), only on the list.
  patient_name?: string | null;
  patient_phone?: string | null;
  reference_id?: string | null;
  appointment_scheduled_at?: string | null;
};

const REFUNDS_QUERY_KEY = ["portal-refunds"] as const;

/** The cancel/refund approval queue -- GET/POST /api/portal/refunds*, for a
 * hospital that turned auto_refund_enabled off (Settings -> Appointments).
 * `statusFilter` defaults to the pending_approval tab, the only one staff
 * actually act on; pass "" for every status. */
export function useRefunds(canView: boolean, statusFilter: RefundStatus | "" = "pending_approval") {
  const router = useRouter();
  const queryClient = useQueryClient();

  const {
    data,
    error: queryError,
    isFetching,
  } = useQuery({
    queryKey: [...REFUNDS_QUERY_KEY, statusFilter],
    enabled: canView,
    retry: false,
    queryFn: async () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      const result = await portalFetch(`/api/portal/refunds?${params.toString()}`);
      return unwrapPortalResult<RefundRequest[]>(router, result);
    },
  });

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const toggleSelected = (id: number, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };
  const refunds = data ?? [];
  const toggleSelectAll = (checked: boolean) => {
    setSelected(checked ? new Set(refunds.map((r) => r.id)) : new Set());
  };

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: REFUNDS_QUERY_KEY });
  }

  const approveMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/refunds/${id}/approve`, { method: "POST" });
      return unwrapPortalResult<RefundRequest>(router, result);
    },
    onSuccess: () => {
      toast.success("Refund approved");
      invalidate();
    },
    onError: (err) => {
      if (isPortalMutationError(err)) toast.error("Couldn't approve refund", err.message);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason?: string }) => {
      const result = await portalFetch(`/api/portal/refunds/${id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      return unwrapPortalResult<RefundRequest>(router, result);
    },
    onSuccess: () => {
      toast.success("Refund rejected");
      invalidate();
    },
    onError: (err) => {
      if (isPortalMutationError(err)) toast.error("Couldn't reject refund", err.message);
    },
  });

  const syncMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/refunds/${id}/sync`, { method: "POST" });
      return unwrapPortalResult<RefundRequest>(router, result);
    },
    onSuccess: () => invalidate(),
    onError: (err) => {
      if (isPortalMutationError(err)) toast.error("Couldn't check refund status", err.message);
    },
  });

  const bulkApproveMutation = useMutation({
    mutationFn: async (payload: {
      refund_request_ids?: number[];
      date_from?: string;
      date_to?: string;
    }) => {
      const result = await portalFetch("/api/portal/refunds/approve-bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapPortalResult<{ approved_count: number; refunds: RefundRequest[] }>(
        router,
        result,
      );
    },
    onSuccess: (data) => {
      toast.success(
        `${data.approved_count} refund${data.approved_count === 1 ? "" : "s"} approved`,
      );
      setSelected(new Set());
      invalidate();
    },
    onError: (err) => {
      if (isPortalMutationError(err)) toast.error("Couldn't approve refunds", err.message);
    },
  });

  return {
    refunds,
    error: queryError ? "Couldn't load refunds — try again." : null,
    isFetching,
    selected,
    toggleSelected,
    toggleSelectAll,
    approve: approveMutation.mutate,
    approvingId: approveMutation.isPending ? (approveMutation.variables ?? null) : null,
    reject: rejectMutation.mutate,
    rejectingId: rejectMutation.isPending ? (rejectMutation.variables?.id ?? null) : null,
    sync: syncMutation.mutate,
    syncingId: syncMutation.isPending ? (syncMutation.variables ?? null) : null,
    bulkApprove: bulkApproveMutation.mutateAsync,
    bulkApproving: bulkApproveMutation.isPending,
  };
}
