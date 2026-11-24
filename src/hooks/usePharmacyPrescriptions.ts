import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";

export type PrescriptionStatus = "draft" | "pending" | "in_progress" | "completed" | "cancelled";
export type DispenseStage = "queued" | "in_progress" | "ready_for_pickup" | "dispensed";

export type Prescription = {
  id: number;
  patient_id: number | null;
  appointment_id: number | null;
  patient_name: string;
  ward_or_opd: string | null;
  prescribing_doctor_id: string | null;
  doctor_name: string | null;
  status: PrescriptionStatus;
  notes: string | null;
  general_advice: string | null;
  follow_up_date: string | null;
  dispense_stage: DispenseStage;
  assigned_pharmacist_identity_id: number | null;
  assigned_pharmacist_name: string | null;
  created_at: string;
};

export type NewPrescriptionPayload = {
  patient_name: string;
  items: NewPrescriptionItem[];
  patient_id?: number;
  appointment_id?: number;
  prescribing_doctor_id?: string;
  ward_or_opd?: string;
  notes?: string;
  general_advice?: string;
  follow_up_date?: string;
  // "draft" (default, "Save Draft") or "pending" ("Sign & Send to
  // Pharmacy" -- skips the draft stage entirely rather than create-then-
  // immediately-sign in two calls).
  status?: "draft" | "pending";
};

export type PrescriptionItem = {
  id: number;
  medicine_id: number;
  medicine_name: string;
  quantity_prescribed: number;
  quantity_dispensed: number;
  dosage_instructions: string | null;
  dosage: string | null;
  frequency: string | null;
  duration: string | null;
};

export type PrescriptionFull = Prescription & { items: PrescriptionItem[] };

// quantity_prescribed is optional -- the New Prescription form's medicine
// table no longer collects a raw quantity, only Dosage/Frequency/Duration/
// Instructions; the backend derives it from frequency+duration when
// omitted (see pharmacy_prescriptions.py's _derive_quantity()).
export type NewPrescriptionItem = {
  medicine_id: number;
  quantity_prescribed?: number;
  dosage_instructions?: string;
  dosage?: string;
  frequency?: string;
  duration?: string;
};

function queryKey(status?: string) {
  return ["portal-pharmacy-prescriptions", status ?? "all"];
}

export function usePharmacyPrescriptions(ready: boolean, status?: PrescriptionStatus) {
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: queryKey(status),
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const qs = status ? `?status=${status}` : "";
      const result = await portalFetch(`/api/portal/pharmacy/prescriptions${qs}`);
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
      return (result.data as { prescriptions: Prescription[] }).prescriptions;
    },
  });

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-prescriptions"] });
    queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-inventory"] });
    queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-medicines"] });
    queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-billing-sales"] });
  }

  const createMutation = useMutation({
    mutationFn: async (payload: NewPrescriptionPayload) => {
      const result = await portalFetch("/api/portal/pharmacy/prescriptions", {
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
      toast.success("Prescription created");
      invalidateAll();
    },
    onError: (err) => toast.error("Couldn't create prescription", err instanceof Error ? err.message : "Try again."),
  });

  const signMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/pharmacy/prescriptions/${id}/sign`, { method: "POST" });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Signed and sent to pharmacy");
      invalidateAll();
    },
    onError: (err) => toast.error("Couldn't sign prescription", err instanceof Error ? err.message : "Try again."),
  });

  const cancelMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/pharmacy/prescriptions/${id}/cancel`, { method: "POST" });
      if (!result.ok) throw new Error(result.unauthorized ? "Session expired." : result.error);
    },
    onSuccess: () => {
      toast.success("Prescription cancelled");
      invalidateAll();
    },
    onError: (err) => toast.error("Couldn't cancel prescription", err instanceof Error ? err.message : "Try again."),
  });

  const dispenseMutation = useMutation({
    mutationFn: async ({ id, items }: { id: number; items: { prescription_item_id: number; quantity: number }[] }) => {
      const result = await portalFetch(`/api/portal/pharmacy/prescriptions/${id}/dispense`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired." : (result.body?.errors as string[] | undefined)?.join(" ") || result.error,
        );
      }
    },
    onSuccess: () => {
      toast.success("Dispensed");
      invalidateAll();
    },
    onError: (err) => toast.error("Couldn't dispense", err instanceof Error ? err.message : "Try again."),
  });

  return {
    prescriptions: data ?? [],
    error: error instanceof Error ? error.message : null,
    isLoading,
    createPrescription: (payload: NewPrescriptionPayload) => createMutation.mutateAsync(payload),
    creating: createMutation.isPending,
    signPrescription: (id: number) => signMutation.mutateAsync(id),
    signing: signMutation.isPending,
    cancelPrescription: (id: number) => cancelMutation.mutateAsync(id),
    dispense: (id: number, items: { prescription_item_id: number; quantity: number }[]) =>
      dispenseMutation.mutateAsync({ id, items }),
    dispensing: dispenseMutation.isPending,
  };
}

export async function fetchPrescription(id: number): Promise<PrescriptionFull | null> {
  const result = await portalFetch(`/api/portal/pharmacy/prescriptions/${id}`);
  if (!result.ok) return null;
  return (result.data as { prescription: PrescriptionFull }).prescription;
}
