"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, PackageCheck, Pill, Plus, Printer, Receipt, Send, Timer } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { DataTable } from "@/components/ui/DataTable";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { Input } from "@/components/ui/Input";
import { QuickActions } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { PatientStatTileRow } from "./PatientStatTileRow";
import { formatShortDateTime } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { fetchPrescription, usePharmacyPrescriptions, type Prescription } from "@/hooks/usePharmacyPrescriptions";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { usePharmacyUnits } from "@/hooks/usePharmacySettings";
import { NewPrescriptionDialog, type PrescriptionPrefill } from "../../pharmacy/prescriptions/_components/NewPrescriptionDialog";
import { PRESCRIPTION_STATUS_LABELS, PRESCRIPTION_STATUS_TONES } from "../../pharmacy/prescriptions/_components/prescriptions-columns";

type Props = {
  patientId: number;
  patientName: string;
  onViewBilling?: () => void;
};

const DISPENSE_STAGE_LABELS: Record<string, string> = {
  queued: "Pending Pharmacy", in_progress: "In Progress", ready_for_pickup: "Ready for Pickup", dispensed: "Dispensed",
};

/** The patient detail page's "Prescriptions" tab -- every prescription ever
 * written for this patient, hospital-wide, not scoped to one visit. Reuses
 * the same hooks/dialog/status vocabulary as the standalone /portal/pharmacy/
 * prescriptions queue, laid out master-detail (list left, selected
 * prescription + its medicines + quick actions right) to match the Patient
 * Details page's other tabs. The full pick/pack/handover dispensing
 * workflow stays on the dedicated Dispensing page -- this tab keeps only
 * "Sign & Send to Pharmacy" (draft -> pending), a natural action from the
 * patient's own record. */
export function PatientPrescriptionsPanel({ patientId, patientName, onViewBilling }: Props) {
  const canPrescribe = usePermission("prescriptions", "write");
  const { prescriptions, createPrescription, creating, signPrescription, signing } = usePharmacyPrescriptions(true);
  const { medicines } = useMedicines(true);
  const { units } = usePharmacyUnits(true);
  const dosageForms = units.filter((u) => u.kind === "dosage_form");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [pharmacyStatusFilter, setPharmacyStatusFilter] = useState("all");

  const own = prescriptions.filter((p) => p.patient_id === patientId);
  const filtered = own.filter((p) => {
    if (statusFilter !== "all" && p.status !== statusFilter) return false;
    if (pharmacyStatusFilter !== "all" && p.dispense_stage !== pharmacyStatusFilter) return false;
    if (search.trim() && !String(p.id).includes(search.trim()) && !(p.doctor_name || "").toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  });
  const selected = own.find((p) => p.id === selectedId) || filtered[0] || own[0] || null;
  const prefill: PrescriptionPrefill = { patientId, patientName };

  const { data: full } = useQuery({
    queryKey: ["portal-pharmacy-prescription", selected?.id ?? null],
    enabled: !!selected,
    queryFn: () => fetchPrescription(selected!.id),
  });

  const sentToPharmacy = own.filter((p) => p.status === "pending" || p.status === "in_progress").length;
  const dispensed = own.filter((p) => p.dispense_stage === "dispensed").length;
  const pendingPharmacy = own.filter((p) => p.dispense_stage === "queued").length;

  return (
    <>
      <PatientStatTileRow>
        <StatTile label="Total Prescriptions" value={own.length} icon={ClipboardList} />
        <StatTile label="Sent to Pharmacy" value={sentToPharmacy} icon={Send} tint="clay" />
        <StatTile label="Dispensed" value={dispensed} icon={PackageCheck} tint="success" />
        <StatTile label="Pending Pharmacy" value={pendingPharmacy} icon={Timer} tint="clay" />
        <StatTile label="Active Medicines" value={full ? full.items.length : null} icon={Pill} />
      </PatientStatTileRow>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4">
            <div className="mb-space-3 flex items-center justify-between">
              <p className="text-hint text-[12.5px]">Every prescription written for this patient, across all visits.</p>
              {canPrescribe && (
                <Button onClick={() => setDialogOpen(true)}>
                  <Plus size={15} /> New Prescription
                </Button>
              )}
            </div>

            <div className="mb-space-3 gap-space-2 flex flex-wrap items-center">
              <Input placeholder="Search by prescription ID, doctor…" value={search} onChange={(e) => setSearch(e.target.value)} className="h-9 min-w-50 flex-1" />
              <FilterSelect
                value={statusFilter} onChange={setStatusFilter} allLabel="All Status"
                options={Object.entries(PRESCRIPTION_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
              />
              <FilterSelect
                value={pharmacyStatusFilter} onChange={setPharmacyStatusFilter} allLabel="All Pharmacy Status"
                options={Object.entries(DISPENSE_STAGE_LABELS).map(([value, label]) => ({ value, label }))}
              />
            </div>

            {filtered.length === 0 ? (
              <p className="py-space-4 text-ink-400 text-center text-[13px]">No prescriptions match.</p>
            ) : (
              <DataTable
                columns={[
                  { id: "id", header: "RX #", cell: ({ row }: { row: { original: Prescription } }) => (
                    <span className="text-brand-700 font-mono text-[12px] font-semibold">RX{row.original.id}</span>
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
                  { id: "dispense_stage", header: "Pharmacy Status", cell: ({ row }: { row: { original: Prescription } }) => (
                    <Badge tone="clay">{DISPENSE_STAGE_LABELS[row.original.dispense_stage] ?? row.original.dispense_stage}</Badge>
                  ) },
                ]}
                data={filtered}
                getRowId={(p: Prescription) => String(p.id)}
                onRowClick={(p: Prescription) => setSelectedId(p.id)}
                rowClassName={(p: Prescription) => (selected?.id === p.id ? "bg-brand-50" : "")}
                pageSize={10}
                tableId="patient-prescriptions"
              />
            )}
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Selected Prescription Details</h3>
            {!selected || !full ? (
              selected ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-3 w-full" />
                  ))}
                </div>
              ) : (
                <p className="text-hint text-[12.5px]">No prescriptions yet.</p>
              )
            ) : (
              <>
                <dl className="space-y-space-2 text-[12.5px]">
                  <div className="flex justify-between"><dt className="text-hint">Prescription ID</dt><dd className="text-ink-900 font-mono font-semibold">RX{full.id}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Prescribed By</dt><dd className="text-ink-900 font-semibold">{full.doctor_name || "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Appointment Ref.</dt><dd className="text-ink-900 font-semibold">{full.appointment_id ? `APT-${full.appointment_id}` : "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Created On</dt><dd className="text-ink-900 font-semibold">{formatShortDateTime(full.created_at)}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Medicines Count</dt><dd className="text-ink-900 font-semibold">{full.items.length}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Pharmacy Status</dt><dd><Badge tone="clay">{DISPENSE_STAGE_LABELS[full.dispense_stage] ?? full.dispense_stage}</Badge></dd></div>
                </dl>

                <p className="text-ink-900 mt-space-4 mb-space-2 text-[12.5px] font-bold">Medicines ({full.items.length})</p>
                <table className="w-full text-[12px]">
                  <thead><tr className="text-hint text-left"><th className="py-space-1">#</th><th className="py-space-1">Medicine (Strength)</th><th className="py-space-1 text-right">Quantity</th></tr></thead>
                  <tbody className="divide-line divide-y">
                    {full.items.map((item, i) => (
                      <tr key={item.id}>
                        <td className="py-space-1 text-ink-600">{i + 1}</td>
                        <td className="py-space-1 text-ink-900 font-medium">{item.medicine_name}</td>
                        <td className="py-space-1 text-ink-900 text-right">{item.quantity_prescribed}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </Card>

          <QuickActions
            title="Quick Actions"
            actions={[
              { label: "Print", icon: Printer, onClick: () => window.print(), disabled: !selected },
              {
                label: signing ? "Sending…" : "Send to Pharmacy",
                icon: Send,
                disabled: !(canPrescribe && full?.status === "draft") || signing,
                onClick: () => signPrescription(full!.id),
              },
              ...(onViewBilling
                ? [{ label: "View Billing", icon: Receipt, onClick: onViewBilling, disabled: !selected }]
                : []),
            ]}
          />
        </div>
      </div>

      <Card className="p-space-4 mt-space-4">
        <h3 className="text-label mb-space-3 text-ink-900 font-bold">Prescription Notes / Advice</h3>
        {!full?.general_advice ? (
          <p className="text-hint text-[12.5px]">No advice recorded for this prescription.</p>
        ) : (
          <ul className="list-disc space-y-space-1 pl-space-5 text-[12.5px]">
            {full.general_advice.split("\n").filter(Boolean).map((line, i) => (
              <li key={i} className="text-ink-700">{line}</li>
            ))}
          </ul>
        )}
      </Card>

      <NewPrescriptionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        medicines={medicines}
        dosageForms={dosageForms}
        onSubmit={createPrescription}
        submitting={creating}
        prefill={prefill}
      />
    </>
  );
}
