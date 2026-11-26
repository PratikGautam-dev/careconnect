"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Boxes, CheckCircle2, Clock, Eye, MoreHorizontal, Pill, Plus, Printer, RotateCcw, Search, XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { portalFetch } from "@/lib/portalAuth";
import { formatShortDateTime } from "@/lib/formatDate";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { usePharmacyUnits } from "@/hooks/usePharmacySettings";
import {
  fetchPrescription, usePharmacyPrescriptions, type Prescription,
} from "@/hooks/usePharmacyPrescriptions";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NewPrescriptionDialog } from "./_components/NewPrescriptionDialog";

// This page's own wording for the pharmacy queue (Pending/In Dispensing/
// Dispensed) -- a relabeling of the same `status` field the rest of the
// app calls Pending/In Progress/Completed (prescriptions-columns.tsx),
// kept local to this file rather than changed everywhere else. There's no
// separate "Ready for pickup, awaiting billing" status in this data model
// (dispense_prescription() creates the pharmacy bill the moment any
// quantity is dispensed) -- so unlike the reference mock, this page has no
// extra "Issue Bill" row action beyond Dispense/Continue/View.
const QUEUE_LABELS: Record<Prescription["status"], string> = {
  draft: "Draft", pending: "Pending", in_progress: "In Dispensing", completed: "Dispensed", cancelled: "Cancelled",
};
const QUEUE_TONES: Record<Prescription["status"], "success" | "clay" | "neutral" | "brand"> = {
  draft: "neutral", pending: "clay", in_progress: "brand", completed: "success", cancelled: "neutral",
};

type Tab = "all" | "pending" | "in_progress" | "completed";
const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "in_progress", label: "In Dispensing" },
  { key: "completed", label: "Dispensed" },
];

type BookingContext = { doctors_by_department: Record<string, { id: string; name: string }[]> };

export default function PrescriptionsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");
  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");
  const [doctorFilter, setDoctorFilter] = useState("all");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { prescriptions, isLoading, createPrescription, creating, cancelPrescription } = usePharmacyPrescriptions(ready);
  const { medicines } = useMedicines(ready);
  const { units } = usePharmacyUnits(ready);
  const dosageForms = units.filter((u) => u.kind === "dosage_form");

  const { data: ctx } = useQuery({
    queryKey: ["portal-new-booking-context"],
    enabled: ready,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/new-booking/context");
      return result.ok ? (result.data as BookingContext) : null;
    },
  });
  const doctorOptions = Object.values(ctx?.doctors_by_department ?? {}).flat();

  // Drafts haven't been sent to the pharmacy yet -- this page is the
  // pharmacy's own queue, so they're excluded entirely (same reasoning as
  // the Dispensing page's own queue).
  const queue = prescriptions.filter((p) => p.status !== "draft");
  const counts = {
    total: queue.length,
    pending: queue.filter((p) => p.status === "pending").length,
    in_progress: queue.filter((p) => p.status === "in_progress").length,
    completed: queue.filter((p) => p.status === "completed").length,
  };

  const filtered = queue.filter((p) => {
    if (tab !== "all" && p.status !== tab) return false;
    if (doctorFilter !== "all" && p.prescribing_doctor_id !== doctorFilter) return false;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      if (!String(p.id).includes(q) && !p.patient_name.toLowerCase().includes(q) && !(p.doctor_name || "").toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const selected = queue.find((p) => p.id === selectedId) || filtered[0] || null;
  const { data: full } = useQuery({
    queryKey: ["portal-pharmacy-prescription", selected?.id ?? null],
    enabled: !!selected,
    queryFn: () => fetchPrescription(selected!.id),
  });

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-prescriptions">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  const active = selected && (selected.status === "pending" || selected.status === "in_progress");

  return (
    <PortalShell hospital={hospital} active="pharmacy-prescriptions">
      <PageHeader title="Prescriptions" description="View and process doctor prescriptions from OPD/IPD." />

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Total Prescriptions" value={counts.total} icon={Pill} />
        <StatTile label="Pending" value={counts.pending} icon={Clock} tint="clay" />
        <StatTile label="In Dispensing" value={counts.in_progress} icon={Boxes} tint="brand" />
        <StatTile label="Dispensed" value={counts.completed} icon={CheckCircle2} tint="success" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2 min-w-0">
          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-1 border-line bg-paper flex w-fit flex-wrap rounded-lg border p-1">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setTab(t.key)}
                  className={`px-space-3 py-space-1 rounded-md text-[12.5px] font-semibold transition-colors duration-150 ${
                    tab === t.key ? "bg-brand-600 text-white" : "text-ink-600 hover:bg-black/4"
                  }`}
                >
                  {t.label} ({counts[t.key === "all" ? "total" : t.key]})
                </button>
              ))}
            </div>

            <div className="mb-space-3 gap-space-2 flex flex-wrap items-center justify-between">
              <div className="gap-space-2 flex flex-1 flex-wrap items-center">
                <div className="relative min-w-50 flex-1">
                  <Search size={14} className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2" />
                  <input
                    type="text" placeholder="Search by Prescription ID, Patient, Doctor…"
                    value={search} onChange={(e) => setSearch(e.target.value)}
                    className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
                  />
                </div>
                <Button variant="secondary" onClick={() => setFiltersOpen((o) => !o)}>Filters</Button>
              </div>
              {canWrite && (
                <Button onClick={() => setDialogOpen(true)}>
                  <Plus size={15} /> New Prescription
                </Button>
              )}
            </div>

            {filtersOpen && (
              <div className="mb-space-3">
                <select
                  value={doctorFilter} onChange={(e) => setDoctorFilter(e.target.value)}
                  className="border-line bg-card px-space-3 text-ink-900 h-9 rounded-md border text-[12.5px]"
                >
                  <option value="all">All Doctors</option>
                  {doctorOptions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>
            )}

            <DataTable
              columns={[
                { id: "id", header: "Prescription ID", cell: ({ row }: { row: { original: Prescription } }) => (
                  <button type="button" onClick={() => setSelectedId(row.original.id)} className="text-brand-700 font-mono text-[12px] font-semibold hover:underline">
                    RX-{row.original.id}
                  </button>
                ) },
                { id: "patient_name", header: "Patient", cell: ({ row }: { row: { original: Prescription } }) => <span className="text-ink-900 font-semibold">{row.original.patient_name}</span> },
                { id: "doctor_name", header: "Doctor", cell: ({ row }: { row: { original: Prescription } }) => <span className="text-ink-600">{row.original.doctor_name || "—"}</span> },
                { id: "created_at", header: "Date & Time", cell: ({ row }: { row: { original: Prescription } }) => <span className="text-ink-600">{formatShortDateTime(row.original.created_at)}</span> },
                { id: "status", header: "Status", cell: ({ row }: { row: { original: Prescription } }) => <Badge tone={QUEUE_TONES[row.original.status]}>{QUEUE_LABELS[row.original.status]}</Badge> },
                { id: "actions", header: "Actions", enableHiding: false, cell: ({ row }: { row: { original: Prescription } }) => {
                  const p = row.original;
                  const label = p.status === "pending" ? "Dispense" : p.status === "in_progress" ? "Continue" : "View";
                  const cancellable = p.status === "pending" || p.status === "in_progress";
                  return (
                    <div onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger className="text-ink-600 hover:text-ink-900 inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-black/4" aria-label={`More actions for RX-${p.id}`}>
                          <MoreHorizontal size={16} />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent>
                          <DropdownMenuGroup>
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuItem onClick={() => router.push(`/portal/pharmacy/prescriptions/${p.id}`)}>
                              <Eye size={14} /> {label}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => window.print()}>
                              <Printer size={14} /> Print
                            </DropdownMenuItem>
                            {canWrite && cancellable && (
                              <DropdownMenuItem variant="destructive" onClick={() => cancelPrescription(p.id)}>
                                <XCircle size={14} /> Cancel Prescription
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuGroup>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  );
                } },
              ]}
              data={filtered}
              getRowId={(p: Prescription) => String(p.id)}
              onRowClick={(p: Prescription) => setSelectedId(p.id)}
              rowClassName={(p: Prescription) => (selected?.id === p.id ? "bg-brand-50" : "")}
              loading={isLoading}
              emptyMessage="No prescriptions in this queue."
              pageSize={10}
              pageSizeOptions={[10, 25, 50]}
              tableId="pharmacy-prescriptions"
            />
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Prescription Details</h3>
            {!selected ? (
              <p className="text-hint text-[12.5px]">No prescriptions yet.</p>
            ) : (
              <>
                <div className="mb-space-3 flex items-center justify-between">
                  <span className="text-ink-900 font-mono text-[14px] font-bold">RX-{selected.id}</span>
                  <Badge tone={QUEUE_TONES[selected.status]}>{QUEUE_LABELS[selected.status]}</Badge>
                </div>
                <dl className="space-y-space-2 text-[12.5px]">
                  <div className="flex justify-between"><dt className="text-hint">Patient</dt><dd className="text-ink-900 font-semibold">{selected.patient_name}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Doctor</dt><dd className="text-ink-900 font-semibold">{selected.doctor_name || "—"}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Date & Time</dt><dd className="text-ink-900 font-semibold">{formatShortDateTime(selected.created_at)}</dd></div>
                  <div className="flex justify-between"><dt className="text-hint">Total Items</dt><dd className="text-ink-900 font-semibold">{full?.items.length ?? "—"}</dd></div>
                </dl>
              </>
            )}
          </Card>

          {selected && (
            <Card className="p-space-4">
              <h3 className="text-label mb-space-3 text-ink-900 font-bold">Prescription Items</h3>
              {!full ? (
                <p className="text-hint text-[12.5px]">Loading…</p>
              ) : (
                <div className="space-y-space-2">
                  {full.items.map((item) => (
                    <div key={item.id} className="border-line flex items-center justify-between rounded-md border p-2.5">
                      <div>
                        <p className="text-ink-900 text-[12.5px] font-semibold">{item.medicine_name}</p>
                        <p className="text-hint text-[11px]">{[item.dosage, item.frequency, item.duration].filter(Boolean).join(" · ") || "—"}</p>
                      </div>
                      <Badge tone="neutral">Qty {item.quantity_prescribed}</Badge>
                    </div>
                  ))}
                </div>
              )}
              {canWrite && active && (
                <Button href={`/portal/pharmacy/prescriptions/${selected.id}`} className="mt-space-4 w-full">
                  <Pill size={14} /> Start Dispensing
                </Button>
              )}
              {!active && (
                <Button href={`/portal/pharmacy/prescriptions/${selected.id}`} variant="secondary" className="mt-space-4 w-full">
                  View Details
                </Button>
              )}
            </Card>
          )}

          <Card className="p-space-4">
            <h3 className="text-label mb-space-3 text-ink-900 font-bold">Quick Actions</h3>
            <div className="gap-space-2 grid grid-cols-2">
              {canWrite && (
                <Button size="md" variant="secondary" onClick={() => setDialogOpen(true)}>
                  <Plus size={14} /> New Prescription
                </Button>
              )}
              <Button size="md" variant="secondary" onClick={() => window.print()}>
                <Printer size={14} /> Print Prescription
              </Button>
              <Button size="md" variant="secondary" href="/portal/pharmacy/returns">
                <RotateCcw size={14} /> Process Return
              </Button>
              <Button size="md" variant="secondary" href="/portal/pharmacy/inventory">
                <Boxes size={14} /> Check Inventory
              </Button>
            </div>
          </Card>
        </div>
      </div>

      <NewPrescriptionDialog open={dialogOpen} onOpenChange={setDialogOpen} medicines={medicines} dosageForms={dosageForms} onSubmit={createPrescription} submitting={creating} />
    </PortalShell>
  );
}
