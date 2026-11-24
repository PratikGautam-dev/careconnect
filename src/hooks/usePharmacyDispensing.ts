import { useMutation, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";
import type { PrescriptionFull } from "@/hooks/usePharmacyPrescriptions";

function invalidate(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-prescriptions"] });
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-prescription"] });
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-inventory"] });
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-medicines"] });
  queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-dashboard"] });
}

/** The dedicated Dispensing page's own workflow transitions -- orthogonal
 * to usePharmacyPrescriptions' create/sign/cancel/dispense (the simpler,
 * one-shot "pick quantities and dispense now" surfaces embedded elsewhere).
 * See portal/routes/pharmacy.py's "Dispensing workflow" section and
 * pharmacy_prescriptions.py's mark_ready_for_pickup() docstring for why
 * stock only actually moves at the "Ready for Pickup" step. */
export function usePharmacyDispensing() {
  const queryClient = useQueryClient();

  async function post(path: string, body?: unknown) {
    const result = await portalFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!result.ok) {
      throw new Error(
        result.unauthorized ? "Session expired." : (result.body?.errors as string[] | undefined)?.join(" ") || result.error,
      );
    }
    return (result.data as { prescription: PrescriptionFull }).prescription;
  }

  const assignMutation = useMutation({
    mutationFn: ({ id, pharmacistId }: { id: number; pharmacistId: number | null }) =>
      post(`/api/portal/pharmacy/dispensing/${id}/assign`, { pharmacist_identity_id: pharmacistId }),
    onSuccess: () => invalidate(queryClient),
    onError: (err) => toast.error("Couldn't assign pharmacist", err instanceof Error ? err.message : "Try again."),
  });

  const startMutation = useMutation({
    mutationFn: (id: number) => post(`/api/portal/pharmacy/dispensing/${id}/start`),
    onSuccess: () => { toast.success("Dispensing started"); invalidate(queryClient); },
    onError: (err) => toast.error("Couldn't start dispensing", err instanceof Error ? err.message : "Try again."),
  });

  const readyMutation = useMutation({
    mutationFn: (id: number) => post(`/api/portal/pharmacy/dispensing/${id}/ready`),
    onSuccess: () => { toast.success("Marked ready for pickup"); invalidate(queryClient); },
    onError: (err) => toast.error("Couldn't mark ready for pickup", err instanceof Error ? err.message : "Try again."),
  });

  const completeMutation = useMutation({
    mutationFn: (id: number) => post(`/api/portal/pharmacy/dispensing/${id}/complete`),
    onSuccess: () => { toast.success("Marked dispensed"); invalidate(queryClient); },
    onError: (err) => toast.error("Couldn't mark dispensed", err instanceof Error ? err.message : "Try again."),
  });

  return {
    assignPharmacist: (id: number, pharmacistId: number | null) => assignMutation.mutateAsync({ id, pharmacistId }),
    assigning: assignMutation.isPending,
    startDispensing: (id: number) => startMutation.mutateAsync(id),
    starting: startMutation.isPending,
    markReadyForPickup: (id: number) => readyMutation.mutateAsync(id),
    markingReady: readyMutation.isPending,
    markDispensed: (id: number) => completeMutation.mutateAsync(id),
    markingDispensed: completeMutation.isPending,
  };
}
