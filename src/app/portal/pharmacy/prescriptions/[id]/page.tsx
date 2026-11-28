"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatShortDateTime } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { fetchPrescription, usePharmacyPrescriptions } from "@/hooks/usePharmacyPrescriptions";
import { toast } from "@/lib/toast";
import { PRESCRIPTION_STATUS_LABELS, PRESCRIPTION_STATUS_TONES } from "../_components/prescriptions-columns";

export default function PrescriptionDetailPage() {
  const params = useParams<{ id: string }>();
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { cancelPrescription, signPrescription, signing, dispense, dispensing } = usePharmacyPrescriptions(false);
  const queryClient = useQueryClient();
  const queryKey = ["portal-pharmacy-prescription", params.id];
  const { data: prescription, isLoading: loading } = useQuery({
    queryKey,
    enabled: ready,
    retry: false,
    queryFn: () => fetchPrescription(Number(params.id)),
  });
  const [dispenseQty, setDispenseQty] = useState<Record<number, string>>({});
  // Pre-fills each item's input with its own full remaining quantity the
  // moment this prescription's data loads, so clicking "Dispense Medicine"
  // works immediately for the common "dispense everything" case -- the
  // "Up to N" placeholder text alone wasn't enough of a cue: staff read it
  // as the box already holding that amount, typed nothing, and the dispense
  // call silently found zero quantities to act on. Re-keyed off the
  // prescription id (not every render) so a staff member's own edits mid-
  // session are never clobbered by a background refetch.
  const [prefilledForId, setPrefilledForId] = useState<number | null>(null);
  if (prescription && prefilledForId !== prescription.id) {
    const defaults: Record<number, string> = {};
    for (const item of prescription.items) {
      const remaining = item.quantity_prescribed - item.quantity_dispensed;
      if (remaining > 0) defaults[item.id] = String(remaining);
    }
    setDispenseQty(defaults);
    setPrefilledForId(prescription.id);
  }

  function load() {
    queryClient.invalidateQueries({ queryKey });
  }

  if (!hospital) return null;

  const active = prescription && (prescription.status === "pending" || prescription.status === "in_progress");
  const cancellable = prescription && (prescription.status === "draft" || active);

  async function handleDispense() {
    if (!prescription) return;
    const remainingById = new Map(
      prescription.items.map((item) => [item.id, item.quantity_prescribed - item.quantity_dispensed]),
    );
    const touched = prescription.items.filter((item) => (dispenseQty[item.id] || "").trim());
    const items = touched
      .map((item) => ({ prescription_item_id: item.id, quantity: Number(dispenseQty[item.id]) }))
      .filter((i) => Number.isInteger(i.quantity) && i.quantity > 0 && i.quantity <= (remainingById.get(i.prescription_item_id) ?? 0));
    if (items.length === 0) {
      toast.error("Enter at least one quantity to dispense", "Every item's quantity is empty or zero.");
      return;
    }
    if (items.length !== touched.length) {
      toast.error("Check the quantities entered", "Each one must be a whole number, greater than zero, and not more than what's remaining.");
      return;
    }
    try {
      await dispense(prescription.id, items);
      setDispenseQty({});
      load();
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-prescriptions">
      <PageHeader
        title={prescription ? `Prescription for ${prescription.patient_name}` : "Prescription"}
        actions={
          <Button href="/portal/pharmacy/prescriptions" variant="ghost">
            <ChevronLeft size={15} /> Back to Prescriptions
          </Button>
        }
      />
      {loading && (
        <div className="space-y-3">
          <SkeletonCard lines={4} />
          <SkeletonCard lines={3} />
        </div>
      )}
      {!loading && !prescription && <p className="text-hint text-[13px]">No such prescription.</p>}
      {prescription && (
        <div className="space-y-space-4">
          <Card className="p-space-5">
            <div className="gap-space-4 grid grid-cols-2 sm:grid-cols-4">
              <div>
                <p className="text-hint text-[11.5px]">Patient</p>
                <p className="text-ink-900 font-semibold">{prescription.patient_name}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Ward/OPD</p>
                <p className="text-ink-900 font-semibold">{prescription.ward_or_opd || "—"}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Created</p>
                <p className="text-ink-900 font-semibold">{formatShortDateTime(prescription.created_at)}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Status</p>
                <Badge tone={PRESCRIPTION_STATUS_TONES[prescription.status]}>{PRESCRIPTION_STATUS_LABELS[prescription.status]}</Badge>
              </div>
            </div>
          </Card>

          <Card className="p-space-5">
            <p className="text-ink-900 mb-space-3 text-[15px] font-semibold">Items</p>
            <div className="space-y-space-3">
              {prescription.items.map((item) => {
                const remaining = item.quantity_prescribed - item.quantity_dispensed;
                return (
                  <div key={item.id} className="border-line p-space-3 gap-space-3 flex items-center justify-between rounded-md border">
                    <div>
                      <p className="text-ink-900 font-semibold">{item.medicine_name}</p>
                      <p className="text-hint text-[12px]">
                        {[item.dosage, item.frequency, item.duration].filter(Boolean).join(" · ") || "No dosage notes"}
                        {item.dosage_instructions ? ` · ${item.dosage_instructions}` : ""}
                        {` · Prescribed ${item.quantity_prescribed}, Dispensed ${item.quantity_dispensed}`}
                      </p>
                    </div>
                    {canWrite && active && remaining > 0 && (
                      <Input
                        type="number" min="1" max={remaining} step="1" placeholder={`Up to ${remaining}`}
                        value={dispenseQty[item.id] || ""}
                        onChange={(e) => setDispenseQty((q) => ({ ...q, [item.id]: e.target.value }))}
                        className="w-28"
                      />
                    )}
                  </div>
                );
              })}
            </div>
            {prescription.general_advice && (
              <p className="text-hint mt-space-4 text-[12.5px]">
                <span className="text-ink-700 font-semibold">General advice:</span> {prescription.general_advice}
              </p>
            )}
            {prescription.follow_up_date && (
              <p className="text-hint mt-space-1 text-[12.5px]">
                <span className="text-ink-700 font-semibold">Follow-up:</span> {formatShortDateTime(prescription.follow_up_date)}
              </p>
            )}
            {canWrite && (prescription.status === "draft" || active || cancellable) && (
              <div className="gap-space-2 mt-space-4 flex">
                {prescription.status === "draft" && (
                  <Button
                    disabled={signing}
                    onClick={async () => {
                      await signPrescription(prescription.id);
                      load();
                    }}
                  >
                    {signing ? "Sending…" : "Sign & Send to Pharmacy"}
                  </Button>
                )}
                {active && (
                  <Button disabled={dispensing} onClick={handleDispense}>
                    {dispensing ? "Dispensing…" : "Dispense Medicine"}
                  </Button>
                )}
                {cancellable && (
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      try {
                        await cancelPrescription(prescription.id);
                        load();
                      } catch {
                        // Error toast already shown by the mutation's onError.
                      }
                    }}
                  >
                    Cancel Prescription
                  </Button>
                )}
              </div>
            )}
          </Card>
        </div>
      )}
    </PortalShell>
  );
}
