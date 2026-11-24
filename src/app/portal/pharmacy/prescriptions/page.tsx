"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { usePermission } from "@/lib/staffAuth";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { usePharmacyPrescriptions, type PrescriptionStatus } from "@/hooks/usePharmacyPrescriptions";
import { createPrescriptionColumns } from "./_components/prescriptions-columns";
import { NewPrescriptionDialog } from "./_components/NewPrescriptionDialog";

const TABS: { key: PrescriptionStatus | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "draft", label: "Draft" },
  { key: "pending", label: "Pending" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
];

export default function PrescriptionsPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");
  const [tab, setTab] = useState<PrescriptionStatus | "all">("all");
  const { prescriptions, isLoading, createPrescription, creating } = usePharmacyPrescriptions(
    ready, tab === "all" ? undefined : tab,
  );
  const { medicines } = useMedicines(ready);
  const [dialogOpen, setDialogOpen] = useState(false);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-prescriptions">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-prescriptions">
      <PageHeader
        title="Prescriptions"
        description="The pharmacy's prescription queue -- open one to dispense it."
        actions={
          canWrite && (
            <Button onClick={() => setDialogOpen(true)}>
              <Plus size={15} /> New Prescription
            </Button>
          )
        }
      />
      <div className="gap-space-2 mb-space-4 flex">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "px-space-4 py-space-2 rounded-full text-[13px] font-semibold transition-colors duration-150",
              tab === t.key ? "bg-brand-600 text-white" : "bg-card border-line text-ink-600 border hover:bg-black/4",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <Card className="p-space-5">
        <DataTable
          columns={createPrescriptionColumns()}
          data={prescriptions}
          getRowId={(p) => String(p.id)}
          loading={isLoading}
          emptyMessage="No prescriptions in this queue."
          pageSizeOptions={[10, 25, 50]}
          tableId="pharmacy-prescriptions"
          onRowClick={(p) => router.push(`/portal/pharmacy/prescriptions/${p.id}`)}
        />
      </Card>

      <NewPrescriptionDialog open={dialogOpen} onOpenChange={setDialogOpen} medicines={medicines} onSubmit={createPrescription} submitting={creating} />
    </PortalShell>
  );
}
