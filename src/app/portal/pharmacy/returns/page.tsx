"use client";

import { useMemo, useState } from "react";
import { Package, PackageOpen, Plus, RotateCcw, Search, Wallet } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { QuickActions } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { VisitTypeDonut } from "../../report-analytics/_components/VisitTypeDonut";
import { cn } from "@/lib/cn";
import { formatINR } from "@/lib/formatCurrency";
import { usePermission } from "@/lib/staffAuth";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { usePharmacySuppliers } from "@/hooks/usePharmacySuppliers";
import {
  usePurchaseReturns, useReturnsSummary, useSalesReturns, useStockAdjustments,
} from "@/hooks/usePharmacyReturns";
import { createReturnColumns, type ReturnRow } from "./_components/returns-columns";
import { CreateReturnDialog, type ReturnTab } from "./_components/CreateReturnDialog";

const TABS: { key: ReturnTab; label: string }[] = [
  { key: "sales_return", label: "Sales Returns" },
  { key: "purchase_return", label: "Purchase Returns" },
  { key: "stock_adjustment", label: "Stock Adjustments" },
];

export default function ReturnsAndAdjustmentsPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");

  const { summary } = useReturnsSummary(ready);
  const { returns: salesReturns, createReturn: createSalesReturn, creating: creatingSales } = useSalesReturns(ready);
  const { returns: purchaseReturns, createReturn: createPurchaseReturn, creating: creatingPurchase } = usePurchaseReturns(ready);
  const { adjustments, createAdjustment, creating: creatingAdjustment } = useStockAdjustments(ready);
  const { medicines } = useMedicines(ready);
  const { suppliers } = usePharmacySuppliers(ready);

  const [tab, setTab] = useState<ReturnTab>("sales_return");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  const rowsByTab: Record<ReturnTab, ReturnRow[]> = {
    sales_return: salesReturns,
    purchase_return: purchaseReturns,
    stock_adjustment: adjustments,
  };
  const rows = rowsByTab[tab];
  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.trim().toLowerCase();
    return rows.filter(
      (r) => r.return_number.toLowerCase().includes(q) || r.reference_label.toLowerCase().includes(q) || r.party_label.toLowerCase().includes(q),
    );
  }, [rows, search]);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-returns">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-returns">
      <PageHeader
        title="Returns & Adjustments"
        description="Manage sales returns, purchase returns, damaged stock, and inventory adjustments."
        actions={
          canWrite && (
            <Button onClick={() => setDialogOpen(true)}>
              <Plus size={15} /> Create Return
            </Button>
          )
        }
      />

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Sales Returns" value={summary?.sales_returns_count ?? 0} icon={RotateCcw} tint="clay" />
        <StatTile label="Purchase Returns" value={summary?.purchase_returns_count ?? 0} icon={Package} tint="brand" />
        <StatTile label="Pending Adjustments" value={summary?.pending_adjustments_count ?? 0} icon={PackageOpen} tint="error" />
        <StatTile label="Adjustment Value" value={formatINR(summary?.adjustment_value ?? 0)} icon={Wallet} tint="success" />
      </StatTileGrid>

      <Card className="p-space-5 mb-space-4">
        <div className="mb-space-3 gap-space-2 flex flex-wrap items-center justify-between">
          <div className="gap-space-2 flex flex-wrap">
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
                {t.label} ({rowsByTab[t.key].length})
              </button>
            ))}
          </div>
          <div className="relative w-64">
            <Search size={14} className="text-ink-400 absolute top-1/2 left-space-2 -translate-y-1/2" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by return no., reference, patient, supplier…"
              className="pl-space-6"
            />
          </div>
        </div>

        <DataTable
          columns={createReturnColumns()}
          data={filtered}
          getRowId={(r) => `${r.type}-${r.id}`}
          emptyMessage="No returns or adjustments yet."
          pageSizeOptions={[10, 25, 50]}
          tableId="pharmacy-returns-adjustments"
        />
      </Card>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <Card className="p-space-4">
          <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Adjustment Summary</p>
          <div className="space-y-space-2 text-[12.5px]">
            <div className="flex justify-between"><span className="text-ink-400">Total Returns</span><span className="text-ink-900 font-semibold">{summary?.total_returns ?? 0}</span></div>
            <div className="flex justify-between"><span className="text-ink-400">Total Adjustments</span><span className="text-ink-900 font-semibold">{summary?.total_adjustments ?? 0}</span></div>
            <div className="flex justify-between"><span className="text-ink-400">Total Value (Returns)</span><span className="text-ink-900 font-semibold">{formatINR(summary?.total_returns_value ?? 0)}</span></div>
            <div className="flex justify-between"><span className="text-ink-400">Total Value (Adjustments)</span><span className="text-ink-900 font-semibold">{formatINR(summary?.total_adjustments_value ?? 0)}</span></div>
            <div className="border-line mt-space-2 flex justify-between border-t pt-space-2">
              <span className="text-ink-700 font-bold">Net Adjustment Value</span>
              <span className="text-brand-700 font-bold">{formatINR(summary?.net_adjustment_value ?? 0)}</span>
            </div>
          </div>
        </Card>

        <VisitTypeDonut title="Return Reasons" data={summary?.return_reasons ?? []} unitLabel="returns" emptyMessage="No sales returns yet." />

        {canWrite && (
          <QuickActions
            title="Quick Actions"
            columns={1}
            actions={[
              { label: "Create Return", icon: Plus, onClick: () => { setTab("sales_return"); setDialogOpen(true); } },
              { label: "Record Damage", icon: PackageOpen, onClick: () => { setTab("stock_adjustment"); setDialogOpen(true); } },
              { label: "Adjust Stock", icon: Package, href: "/portal/pharmacy/inventory" },
            ]}
          />
        )}
      </div>

      <CreateReturnDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        tab={tab === "stock_adjustment" || tab === "purchase_return" ? tab : "sales_return"}
        medicines={medicines}
        suppliers={suppliers}
        submitting={creatingSales || creatingPurchase || creatingAdjustment}
        onSubmitSalesReturn={createSalesReturn}
        onSubmitPurchaseReturn={createPurchaseReturn}
        onSubmitStockAdjustment={createAdjustment}
      />
    </PortalShell>
  );
}
