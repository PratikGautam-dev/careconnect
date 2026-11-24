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
import { usePharmacyBilling, type SaleType } from "@/hooks/usePharmacyBilling";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { createPharmacySaleColumns } from "./_components/pharmacy-sales-columns";
import { NewOtcSaleDialog } from "./_components/NewOtcSaleDialog";

const TABS: { key: SaleType; label: string }[] = [
  { key: "prescription", label: "Prescription Bills" },
  { key: "otc", label: "OTC Sales" },
  { key: "ipd", label: "IPD Bills" },
];

export default function PharmacyBillingPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy_billing", "view");
  const canWrite = usePermission("pharmacy_billing", "write");
  const [tab, setTab] = useState<SaleType>("prescription");
  const [page, setPage] = useState(1);
  const { sales, total, isLoading, createOtcSale, creatingOtcSale } = usePharmacyBilling(ready, undefined, page, tab);
  const { medicines } = useMedicines(ready);
  const [dialogOpen, setDialogOpen] = useState(false);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-billing">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-billing">
      <PageHeader
        title="Pharmacy Billing"
        description="Create bills for prescriptions, OTC sales, and inpatient (IPD) orders."
        actions={
          canWrite && (
            <Button onClick={() => setDialogOpen(true)}>
              <Plus size={15} /> New Bill
            </Button>
          )
        }
      />
      <div className="gap-space-2 mb-space-4 flex flex-wrap">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => { setTab(t.key); setPage(1); }}
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
          columns={createPharmacySaleColumns()}
          data={sales}
          getRowId={(s) => String(s.id)}
          loading={isLoading}
          emptyMessage="No bills in this category yet."
          onRowClick={(s) => router.push(`/portal/pharmacy-billing/${s.id}`)}
          pagination={{ page, limit: 20, total }}
          onPageChange={setPage}
        />
      </Card>

      <NewOtcSaleDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        medicines={medicines}
        submitting={creatingOtcSale}
        onSubmit={createOtcSale}
      />
    </PortalShell>
  );
}
