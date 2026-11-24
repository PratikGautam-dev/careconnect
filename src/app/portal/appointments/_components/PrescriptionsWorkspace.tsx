"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Printer, RotateCcw, Search, Boxes } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { DataTable } from "@/components/ui/DataTable";
import { QuickActions } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { cn } from "@/lib/cn";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import {
  fetchPrescription, usePharmacyPrescriptions, type Prescription,
} from "@/hooks/usePharmacyPrescriptions";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { NewPrescriptionDialog, type PrescriptionPrefill } from "../../pharmacy/prescriptions/_components/NewPrescriptionDialog";
import { PRESCRIPTION_STATUS_LABELS, PRESCRIPTION_STATUS_TONES } from "../../pharmacy/prescriptions/_components/prescriptions-columns";

type Tab = "all" | "draft" | "pending" | "in_progress" | "completed";
const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "draft", label: "Draft" },
  { key: "pending", label: "Pending" },
  { key: "in_progress", label: "In Dispensing" },
  { key: "completed", label: "Dispensed" },
];

type Props = {
  appointmentId: number;
  patientId: number | null;
  patientName: string;
  doctorId: string | null;
  wardOrOpd?: string;
};

/** Embedded "Prescriptions" workspace -- the full hospital-wide queue
 * (list + detail/dispense panel + stat tiles + quick actions), mounted on
 * the appointment detail page rather than its own route, per the reference
 * design. Reuses every piece already built for /portal/pharmacy/prescriptions
 * (hooks, status vocabulary, the NewPrescriptionDialog) rather than a
 * second implementation -- this is the same data, just a different host
 * page. The row for THIS appointment (if a prescription already exists for
 * it) is auto-selected on load so a doctor/pharmacist opening this
 * appointment sees its own prescription first, without losing the ability
 * to look at any other prescription from the same panel. */
export function PrescriptionsWorkspace({ appointmentId, patientId, patientName, doctorId, wardOrOpd }: Props) {
  // Writing a prescription is the doctor-facing action (gated on the
  // narrower "prescriptions" page_key); dispensing affects stock and stays
  // pharmacist-/admin-only ("pharmacy"). See PAGE_PRESCRIPTIONS's comment in
  // the backend's portal/permissions.py for why these are split.
  const canPrescribe = usePermission("prescriptions", "write");
  const canDispense = usePermission("pharmacy", "write");
  const { prescriptions, createPrescription, creating, signPrescription, signing, dispense, dispensing } = usePharmacyPrescriptions(true);
  const { medicines } = useMedicines(true);
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dispenseQty, setDispenseQty] = useState<Record<number, string>>({});
  const [autoSelected, setAutoSelected] = useState(false);

  // Auto-select this appointment's own prescription the first time the
  // list loads one -- a render-phase adjustment (not an effect+setState),
  // so it only ever fires once per mount.
  if (!autoSelected && prescriptions.length > 0) {
    setAutoSelected(true);
    const own = prescriptions.find((p) => p.appointment_id === appointmentId);
    if (own) setSelectedId(own.id);
  }

  const counts = {
    all: prescriptions.length,
    draft: prescriptions.filter((p) => p.status === "draft").length,
    pending: prescriptions.filter((p) => p.status === "pending").length,
    in_progress: prescriptions.filter((p) => p.status === "in_progress").length,
    completed: prescriptions.filter((p) => p.status === "completed").length,
  };

  const filtered = useMemo(() => {
    let rows = prescriptions;
    if (tab !== "all") rows = rows.filter((p) => p.status === tab);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter(
        (p) =>
          p.patient_name.toLowerCase().includes(q) ||
          (p.doctor_name || "").toLowerCase().includes(q) ||
          String(p.id).includes(q),
      );
    }
    return rows;
  }, [prescriptions, tab, search]);

  const detailQueryKey = ["portal-pharmacy-prescription", selectedId];
  const { data: selected } = useQuery({
    queryKey: detailQueryKey,
    enabled: selectedId != null,
    retry: false,
    queryFn: () => fetchPrescription(selectedId as number),
  });

  const [prevSelectedId, setPrevSelectedId] = useState(selectedId);
  if (selectedId !== prevSelectedId) {
    setPrevSelectedId(selectedId);
    setDispenseQty({});
  }

  const active = selected && (selected.status === "pending" || selected.status === "in_progress");

  async function handleDispense() {
    if (!selected) return;
    const items = selected.items
      .map((item) => ({ prescription_item_id: item.id, quantity: Number(dispenseQty[item.id] || 0) }))
      .filter((i) => i.quantity > 0);
    if (items.length === 0) return;
    try {
      await dispense(selected.id, items);
      setDispenseQty({});
      queryClient.invalidateQueries({ queryKey: detailQueryKey });
    } catch {
      // Error toast already shown by the mutation's onError.
    }
  }

  const prefill: PrescriptionPrefill = {
    patientId: patientId ?? undefined,
    patientName,
    appointmentId,
    prescribingDoctorId: doctorId ?? undefined,
    wardOrOpd,
  };

  return (
    <Card className="p-space-5 mt-space-4">
      <div className="mb-space-4 flex items-center justify-between">
        <div>
          <p className="text-ink-900 text-[15px] font-bold">Prescriptions</p>
          <p className="text-hint text-[12.5px]">View and process prescriptions for this patient and across the pharmacy queue.</p>
        </div>
        {canPrescribe && (
          <Button onClick={() => setDialogOpen(true)}>
            <Plus size={15} /> New Prescription
          </Button>
        )}
      </div>

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Total Prescriptions" value={counts.all} icon={Boxes} tint="brand" />
        <StatTile label="Pending" value={counts.pending} icon={Boxes} tint="clay" />
        <StatTile label="In Dispensing" value={counts.in_progress} icon={Boxes} tint="brand" />
        <StatTile label="Dispensed" value={counts.completed} icon={Boxes} tint="success" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="gap-space-2 mb-space-3 flex flex-wrap items-center justify-between">
            <div className="gap-space-2 flex">
              {TABS.map((t) => (
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
            <div className="relative w-56">
              <Search size={14} className="text-ink-400 absolute top-1/2 left-space-2 -translate-y-1/2" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by ID, patient, doctor…"
                className="pl-space-6"
              />
            </div>
          </div>

          <DataTable
            columns={[
              { id: "id", header: "RX #", cell: ({ row }: { row: { original: Prescription } }) => (
                <span className="text-ink-600 font-mono text-[12px]">RX{row.original.id}</span>
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
                <Badge tone={PRESCRIPTION_STATUS_TONES[row.original.status]}>{PRESCRIPTION_STATUS_LABELS[row.original.status]}</Badge>
              ) },
            ]}
            data={filtered}
            getRowId={(p: Prescription) => String(p.id)}
            emptyMessage="No prescriptions match this view."
            pageSizeOptions={[5, 10, 25]}
            tableId="appointment-prescriptions"
            onRowClick={(p: Prescription) => setSelectedId(p.id)}
            rowClassName={(p: Prescription) => (p.id === selectedId ? "bg-brand-50" : "")}
          />
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Prescription Details</p>
            {!selected ? (
              <p className="text-hint py-space-6 text-center text-[12.5px]">Select a prescription to view its details.</p>
            ) : (
              <>
                <p className="text-ink-900 font-mono text-[13px] font-bold">RX{selected.id}</p>
                <div className="space-y-space-1 mt-space-2 text-[12.5px]">
                  <p><span className="text-ink-400">Patient:</span> <span className="text-ink-900 font-medium">{selected.patient_name}</span></p>
                  {selected.doctor_name && <p><span className="text-ink-400">Doctor:</span> <span className="text-ink-900 font-medium">{selected.doctor_name}</span></p>}
                  <p><span className="text-ink-400">Date & Time:</span> <span className="text-ink-900 font-medium">{formatShortDateTime(selected.created_at)}</span></p>
                  <p><span className="text-ink-400">Total Items:</span> <span className="text-ink-900 font-medium">{selected.items.length}</span></p>
                  {selected.follow_up_date && (
                    <p><span className="text-ink-400">Follow-up:</span> <span className="text-ink-900 font-medium">{formatDate(selected.follow_up_date)}</span></p>
                  )}
                </div>

                <p className="text-ink-900 mt-space-4 mb-space-2 text-[12.5px] font-bold">Prescription Items</p>
                <div className="space-y-space-2">
                  {selected.items.map((item) => {
                    const remaining = item.quantity_prescribed - item.quantity_dispensed;
                    return (
                      <div key={item.id} className="border-line p-space-2 rounded-md border">
                        <div className="flex items-center justify-between">
                          <p className="text-ink-900 text-[12.5px] font-semibold">{item.medicine_name}</p>
                          <span className="text-hint text-[11px]">Qty {item.quantity_prescribed}</span>
                        </div>
                        {[item.dosage, item.frequency, item.duration].some(Boolean) && (
                          <p className="text-hint text-[11px]">{[item.dosage, item.frequency, item.duration].filter(Boolean).join(" · ")}</p>
                        )}
                        {item.dosage_instructions && <p className="text-hint text-[11px]">{item.dosage_instructions}</p>}
                        {canDispense && active && remaining > 0 && (
                          <Input
                            type="number" min="1" max={remaining} placeholder={`Up to ${remaining}`}
                            value={dispenseQty[item.id] || ""}
                            onChange={(e) => setDispenseQty((q) => ({ ...q, [item.id]: e.target.value }))}
                            className="mt-space-1 h-8"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>

                {selected.general_advice && (
                  <p className="text-hint mt-space-3 text-[11.5px]">
                    <span className="text-ink-700 font-semibold">General advice:</span> {selected.general_advice}
                  </p>
                )}

                {canPrescribe && selected.status === "draft" && (
                  <Button disabled={signing} onClick={() => signPrescription(selected.id)} className="mt-space-4 w-full">
                    {signing ? "Sending…" : "Sign & Send to Pharmacy"}
                  </Button>
                )}
                {canDispense && active && (
                  <Button disabled={dispensing} onClick={handleDispense} className="mt-space-4 w-full">
                    {dispensing ? "Dispensing…" : "Start Dispensing"}
                  </Button>
                )}
              </>
            )}
          </Card>

          {(canPrescribe || canDispense) && (
            <QuickActions
              title="Quick Actions"
              columns={2}
              actions={[
                { label: "New Prescription", icon: Plus, onClick: () => setDialogOpen(true), disabled: !canPrescribe },
                { label: "Print Prescription", icon: Printer, onClick: () => window.print(), disabled: !selected },
                { label: "Process Return", icon: RotateCcw, disabled: true, title: "Coming soon" },
                { label: "Check Inventory", icon: Boxes, href: "/portal/pharmacy/inventory", disabled: !canDispense },
              ]}
            />
          )}
        </div>
      </div>

      <NewPrescriptionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        medicines={medicines}
        onSubmit={createPrescription}
        submitting={creating}
        prefill={prefill}
      />
    </Card>
  );
}
