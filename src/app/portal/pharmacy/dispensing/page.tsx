"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, Clock, History, Package, PackageCheck, Pill, Printer, StickyNote } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { QuickActions } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { useStaffOptions } from "@/hooks/useStaff";
import { fetchMedicine } from "@/hooks/usePharmacyMedicines";
import {
  fetchPrescription, usePharmacyPrescriptions, type DispenseStage, type Prescription,
} from "@/hooks/usePharmacyPrescriptions";
import { usePharmacyDispensing } from "@/hooks/usePharmacyDispensing";
import { useQuery } from "@tanstack/react-query";

const STAGE_TABS: { key: DispenseStage; label: string }[] = [
  { key: "queued", label: "Queue" },
  { key: "in_progress", label: "In Progress" },
  { key: "ready_for_pickup", label: "Ready" },
  { key: "dispensed", label: "Dispensed" },
];
const STAGE_LABELS: Record<DispenseStage, string> = {
  queued: "Pending", in_progress: "In Progress", ready_for_pickup: "Ready", dispensed: "Dispensed",
};
const STAGE_TONES: Record<DispenseStage, "clay" | "brand" | "neutral" | "success"> = {
  queued: "clay", in_progress: "brand", ready_for_pickup: "neutral", dispensed: "success",
};
const WORKFLOW_STEPS: { key: DispenseStage; label: string }[] = [
  { key: "queued", label: "Queued" },
  { key: "in_progress", label: "Dispensing" },
  { key: "ready_for_pickup", label: "Ready for Pickup" },
  { key: "dispensed", label: "Dispensed" },
];

export default function DispensingPage() {
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const { prescriptions } = usePharmacyPrescriptions(true);
  const { staffOptions } = useStaffOptions(ready);
  const {
    assignPharmacist, assigning, startDispensing, starting, markReadyForPickup, markingReady, markDispensed, markingDispensed,
  } = usePharmacyDispensing();

  const [tab, setTab] = useState<DispenseStage>("queued");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // A draft/cancelled prescription never enters this pipeline.
  const dispensable = prescriptions.filter((p) => p.status !== "draft" && p.status !== "cancelled");
  const counts: Record<DispenseStage, number> = {
    queued: dispensable.filter((p) => p.dispense_stage === "queued").length,
    in_progress: dispensable.filter((p) => p.dispense_stage === "in_progress").length,
    ready_for_pickup: dispensable.filter((p) => p.dispense_stage === "ready_for_pickup").length,
    dispensed: dispensable.filter((p) => p.dispense_stage === "dispensed").length,
  };

  const filtered = useMemo(() => {
    let rows = dispensable.filter((p) => p.dispense_stage === tab);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter((p) => p.patient_name.toLowerCase().includes(q) || (p.doctor_name || "").toLowerCase().includes(q) || String(p.id).includes(q));
    }
    return rows;
  }, [dispensable, tab, search]);

  const detailQueryKey = ["portal-pharmacy-prescription", selectedId];
  const { data: selected } = useQuery({
    queryKey: detailQueryKey,
    enabled: selectedId != null,
    retry: false,
    queryFn: () => fetchPrescription(selectedId as number),
  });

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-dispensing">
      <PageHeader title="Dispensing" description="Process prescriptions, check availability, dispense medicines and track workflow." />

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="To Dispense" value={counts.queued} icon={Pill} tint="clay" />
        <StatTile label="In Progress" value={counts.in_progress} icon={Clock} tint="brand" />
        <StatTile label="Ready for Pickup" value={counts.ready_for_pickup} icon={Package} tint="clay" />
        <StatTile label="Dispensed Today" value={counts.dispensed} icon={PackageCheck} tint="success" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-space-3">
          <div className="gap-space-2 flex flex-wrap items-center justify-between">
            <div className="gap-space-2 flex flex-wrap">
              {STAGE_TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setTab(t.key)}
                  className={cn(
                    "px-space-3 py-space-1 rounded-full text-[12px] font-semibold transition-colors duration-150",
                    tab === t.key ? "bg-brand-600 text-white" : "bg-black/4 text-ink-600 hover:bg-black/6",
                  )}
                >
                  {t.label} ({counts[t.key]})
                </button>
              ))}
            </div>
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by prescription, patient, doctor…" className="w-64" />
          </div>

          <Card className="p-space-4">
            <DataTable
              columns={[
                { id: "id", header: "Prescription ID", cell: ({ row }: { row: { original: Prescription } }) => (
                  <span className="text-brand-700 font-mono text-[12px] font-semibold">RX{row.original.id}</span>
                ) },
                { id: "patient_name", header: "Patient", cell: ({ row }: { row: { original: Prescription } }) => (
                  <span className="text-ink-900 font-semibold">{row.original.patient_name}</span>
                ) },
                { id: "doctor_name", header: "Doctor", cell: ({ row }: { row: { original: Prescription } }) => (
                  <span className="text-ink-600">{row.original.doctor_name || "—"}</span>
                ) },
                { id: "created_at", header: "Date & Time", cell: ({ row }: { row: { original: Prescription } }) => (
                  <span className="text-ink-600">{formatShortDateTime(row.original.created_at)}</span>
                ) },
                { id: "status", header: "Status", cell: ({ row }: { row: { original: Prescription } }) => (
                  <Badge tone={STAGE_TONES[row.original.dispense_stage]}>{STAGE_LABELS[row.original.dispense_stage]}</Badge>
                ) },
              ]}
              data={filtered}
              getRowId={(p: Prescription) => String(p.id)}
              onRowClick={(p: Prescription) => setSelectedId(p.id)}
              rowClassName={(p: Prescription) => (p.id === selectedId ? "bg-brand-50" : "")}
              emptyMessage="Nothing in this column."
              pageSizeOptions={[10, 25, 50]}
              tableId="pharmacy-dispensing-queue"
            />
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <div className="mb-space-3 flex items-center justify-between">
              <p className="text-ink-900 text-[13.5px] font-bold">Prescription Details</p>
              {selected && <Badge tone={STAGE_TONES[selected.dispense_stage]}>{STAGE_LABELS[selected.dispense_stage]}</Badge>}
            </div>
            {!selected ? (
              <p className="text-hint py-space-6 text-center text-[12.5px]">Select a prescription to view its details.</p>
            ) : (
              <>
                <div className="space-y-space-1 text-[12.5px]">
                  <p><span className="text-ink-400">Prescription ID:</span> <span className="text-ink-900 font-mono font-medium">RX{selected.id}</span></p>
                  <p><span className="text-ink-400">Patient:</span> <span className="text-ink-900 font-medium">{selected.patient_name}</span></p>
                  {selected.doctor_name && <p><span className="text-ink-400">Doctor:</span> <span className="text-ink-900 font-medium">{selected.doctor_name}</span></p>}
                  <p><span className="text-ink-400">Date & Time:</span> <span className="text-ink-900 font-medium">{formatShortDateTime(selected.created_at)}</span></p>
                </div>

                <p className="text-ink-900 mt-space-4 mb-space-2 text-[12.5px] font-bold">Medicines ({selected.items.length})</p>
                <div className="space-y-space-2">
                  {selected.items.map((item) => (
                    <MedicineAvailabilityRow key={item.id} medicineId={item.medicine_id} name={item.medicine_name} qty={item.quantity_prescribed} />
                  ))}
                </div>

                <p className="text-ink-900 mt-space-4 mb-space-2 text-[12.5px] font-bold">Pharmacist Assignment</p>
                <select
                  value={selected.assigned_pharmacist_identity_id ?? ""}
                  disabled={!canWrite || assigning}
                  onChange={(e) => assignPharmacist(selected.id, e.target.value ? Number(e.target.value) : null)}
                  className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[12.5px]"
                >
                  <option value="">Unassigned</option>
                  {staffOptions.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>

                <p className="text-ink-900 mt-space-4 mb-space-2 text-[12.5px] font-bold">Dispensing Workflow</p>
                <div className="gap-space-1 flex items-center">
                  {WORKFLOW_STEPS.map((step, i) => {
                    const stepIndex = WORKFLOW_STEPS.findIndex((s) => s.key === selected.dispense_stage);
                    const done = i < stepIndex;
                    const active = i === stepIndex;
                    return (
                      <div key={step.key} className="flex flex-1 flex-col items-center">
                        <span
                          className={cn(
                            "flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold",
                            done ? "bg-success text-white" : active ? "bg-brand-600 text-white" : "bg-black/10 text-ink-400",
                          )}
                        >
                          {done ? <CheckCircle2 size={14} /> : i + 1}
                        </span>
                        <span className="text-hint mt-1 text-center text-[9.5px] leading-tight">{step.label}</span>
                      </div>
                    );
                  })}
                </div>

                {canWrite && (
                  <div className="mt-space-4 space-y-space-2">
                    {selected.dispense_stage === "queued" && (
                      <Button disabled={starting} onClick={() => startDispensing(selected.id)} className="w-full">
                        {starting ? "Starting…" : "Start Dispensing"}
                      </Button>
                    )}
                    {selected.dispense_stage === "in_progress" && (
                      <Button disabled={markingReady} onClick={() => markReadyForPickup(selected.id)} className="w-full">
                        {markingReady ? "Marking ready…" : "Ready for Pickup"}
                      </Button>
                    )}
                    {selected.dispense_stage === "ready_for_pickup" && (
                      <Button disabled={markingDispensed} onClick={() => markDispensed(selected.id)} className="w-full">
                        {markingDispensed ? "Marking dispensed…" : "Mark Dispensed"}
                      </Button>
                    )}
                  </div>
                )}
              </>
            )}
          </Card>

          <QuickActions
            title="Additional Actions"
            columns={2}
            actions={[
              { label: "Print Label", icon: Printer, disabled: true, title: "Coming soon" },
              { label: "Print Invoice", icon: Printer, href: selected?.id ? `/portal/pharmacy-billing` : undefined, disabled: !selected },
              { label: "Add Note", icon: StickyNote, disabled: true, title: "Coming soon" },
              { label: "View History", icon: History, href: "/portal/pharmacy/prescriptions" },
            ]}
          />
        </div>
      </div>
    </PortalShell>
  );
}

function MedicineAvailabilityRow({ medicineId, name, qty }: { medicineId: number; name: string; qty: number }) {
  const { data: medicine } = useQuery({
    queryKey: ["portal-pharmacy-medicine-availability", medicineId],
    queryFn: () => fetchMedicine(medicineId),
  });
  const inStock = medicine ? medicine.quantity_on_hand >= qty : null;
  return (
    <div className="border-line p-space-2 flex items-center justify-between rounded-md border">
      <div>
        <p className="text-ink-900 text-[12.5px] font-semibold">{name}</p>
        <p className="text-hint text-[11px]">Qty {qty}</p>
      </div>
      {inStock === null ? (
        <span className="text-hint text-[11px]">Checking…</span>
      ) : inStock ? (
        <Badge tone="success">In Stock ({medicine?.quantity_on_hand})</Badge>
      ) : (
        <Badge tone="clay">Low Stock ({medicine?.quantity_on_hand})</Badge>
      )}
    </div>
  );
}
