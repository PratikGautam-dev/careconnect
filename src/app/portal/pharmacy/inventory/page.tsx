"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Boxes, Calendar, CheckCircle2, Plus, Upload, Wallet } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/PageHeader";
import { MedicineCsvImport } from "@/components/portal/MedicineCsvImport";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatINR } from "@/lib/formatCurrency";
import { usePermission } from "@/lib/staffAuth";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { usePharmacyInventory } from "@/hooks/usePharmacyInventory";
import { usePharmacySuppliers } from "@/hooks/usePharmacySuppliers";
import { useNearExpiryBatches } from "@/hooks/useStockAlerts";
import { createInventoryColumns } from "./_components/inventory-columns";
import { AddStockDialog } from "./_components/AddStockDialog";
import { VisitTypeDonut } from "../../report-analytics/_components/VisitTypeDonut";

type Tab = "all" | "in_stock" | "low_stock" | "near_expiry";
const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "All Items" },
  { key: "in_stock", label: "In Stock" },
  { key: "low_stock", label: "Low Stock" },
  { key: "near_expiry", label: "Near Expiry" },
];

export default function InventoryPage() {
  const { hospital, ready } = usePortalGuard();
  const queryClient = useQueryClient();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");
  const { inventory, isLoading, addStock, addingStock } = usePharmacyInventory(ready);
  const { medicines } = useMedicines(ready);
  const { suppliers } = usePharmacySuppliers(ready);
  const { nearExpiryBatches } = useNearExpiryBatches(ready);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [csvImportOpen, setCsvImportOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("all");

  const nearExpiryMedicineIds = new Set(nearExpiryBatches.map((b) => b.medicine_id));
  const inStock = inventory.filter((m) => m.quantity_on_hand > 0);
  const lowStock = inventory.filter((m) => m.quantity_on_hand > 0 && m.quantity_on_hand < m.reorder_level);
  const inventoryValue = inventory.reduce((sum, m) => sum + m.quantity_on_hand * (m.unit_price || 0), 0);

  const rowsByTab = {
    all: inventory,
    in_stock: inStock,
    low_stock: lowStock,
    near_expiry: inventory.filter((m) => nearExpiryMedicineIds.has(m.id)),
  };

  const categoryTotals: Record<string, number> = {};
  for (const m of inventory) {
    const cat = m.category || "Uncategorized";
    categoryTotals[cat] = (categoryTotals[cat] || 0) + 1;
  }
  const categoryDistribution = Object.entries(categoryTotals).map(([label, count]) => ({ label, count }));

  const today = new Date();
  const expirySummary = { expired: 0, within30: 0, within90: 0, beyond90: 0 };
  for (const b of nearExpiryBatches) {
    const days = Math.ceil((new Date(b.expiry_date).getTime() - today.getTime()) / 86400000);
    if (days < 0) expirySummary.expired += 1;
    else if (days <= 30) expirySummary.within30 += 1;
    else if (days <= 90) expirySummary.within90 += 1;
    else expirySummary.beyond90 += 1;
  }

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-inventory">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-inventory">
      <PageHeader
        title="Inventory"
        description="Manage medicine stock, batches, expiry and category-wise availability."
        actions={
          canWrite && (
            <div className="gap-space-2 flex">
              <Button href="/portal/pharmacy/medicines" variant="secondary">Manage Medicines</Button>
              <Button variant="secondary" onClick={() => setCsvImportOpen(true)}>
                <Upload size={15} /> Bulk Import
              </Button>
              <Button onClick={() => setDialogOpen(true)}>
                <Plus size={15} /> Add Stock
              </Button>
            </div>
          )
        }
      />

      <StatTileGrid cols={5} className="mb-space-4">
        <StatTile label="Total Items" value={inventory.length} icon={Boxes} tint="brand" />
        <StatTile label="In-Stock Items" value={inStock.length} icon={CheckCircle2} tint="success" />
        <StatTile label="Low-Stock Items" value={lowStock.length} icon={AlertTriangle} tint="clay" />
        <StatTile label="Near-Expiry Items" value={nearExpiryBatches.length} icon={Calendar} tint="error" />
        <StatTile label="Inventory Value" value={formatINR(inventoryValue)} icon={Wallet} tint="brand" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-space-3">
          <div className="gap-space-2 flex flex-wrap">
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
                {t.label} ({rowsByTab[t.key].length})
              </button>
            ))}
          </div>
          <Card className="p-space-5">
            <DataTable
              columns={createInventoryColumns()}
              data={rowsByTab[tab]}
              getRowId={(m) => String(m.id)}
              loading={isLoading}
              emptyMessage="No medicines in this category."
              pageSizeOptions={[10, 25, 50]}
              tableId="pharmacy-inventory"
            />
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Expiry Summary</p>
            <div className="space-y-space-2 text-[12.5px]">
              <div className="flex items-center justify-between"><span className="text-error flex items-center gap-1">● Expired</span><span className="text-ink-900 font-semibold">{expirySummary.expired}</span></div>
              <div className="flex items-center justify-between"><span className="text-clay-700 flex items-center gap-1">● Expiring in ≤ 30 days</span><span className="text-ink-900 font-semibold">{expirySummary.within30}</span></div>
              <div className="flex items-center justify-between"><span className="text-brand-600 flex items-center gap-1">● Expiring in 31–90 days</span><span className="text-ink-900 font-semibold">{expirySummary.within90}</span></div>
              <div className="flex items-center justify-between"><span className="text-success flex items-center gap-1">● Expiring in &gt; 90 days</span><span className="text-ink-900 font-semibold">{inventory.length - expirySummary.expired - expirySummary.within30 - expirySummary.within90}</span></div>
            </div>
          </Card>

          <VisitTypeDonut title="Category Distribution" data={categoryDistribution} unitLabel="items" emptyMessage="No medicines yet." />
        </div>
      </div>

      <AddStockDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        medicines={medicines}
        suppliers={suppliers}
        onSubmit={addStock}
        submitting={addingStock}
      />

      <Dialog open={csvImportOpen} onOpenChange={setCsvImportOpen}>
        <DialogContent className="max-w-3xl">
          <DialogTitle>Bulk import stock from CSV</DialogTitle>
          <MedicineCsvImport
            onImported={() => {
              queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-inventory"] });
              queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-medicines"] });
              queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-suppliers"] });
              queryClient.invalidateQueries({ queryKey: ["portal-pharmacy-near-expiry"] });
              setCsvImportOpen(false);
            }}
          />
        </DialogContent>
      </Dialog>
    </PortalShell>
  );
}
