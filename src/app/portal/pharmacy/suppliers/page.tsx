"use client";

import { useState } from "react";
import { CheckCircle2, Clock, Plus, Search, Trophy, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatINR } from "@/lib/formatCurrency";
import { usePermission } from "@/lib/staffAuth";
import {
  usePharmacySuppliers, useSupplierPurchaseTotals, type Supplier,
} from "@/hooks/usePharmacySuppliers";
import { createSupplierColumns } from "./_components/suppliers-columns";
import { SupplierFormDialog } from "./_components/SupplierFormDialog";
import { VisitTypeDonut } from "../../report-analytics/_components/VisitTypeDonut";

export default function SuppliersPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");
  const { suppliers, isLoading, createSupplier, creating, updateSupplier, updating } = usePharmacySuppliers(ready);
  const { purchaseTotals } = useSupplierPurchaseTotals(ready);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [search, setSearch] = useState("");

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-suppliers">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  const activeSuppliers = suppliers.filter((s) => s.is_active);
  const totalPurchaseValue = Object.values(purchaseTotals).reduce((sum, v) => sum + v, 0);
  const filtered = search.trim()
    ? suppliers.filter((s) => s.name.toLowerCase().includes(search.trim().toLowerCase()))
    : suppliers;

  const categoryTotals: Record<string, number> = {};
  for (const s of suppliers) {
    const cat = s.category || "Others";
    categoryTotals[cat] = (categoryTotals[cat] || 0) + 1;
  }
  const categoryDistribution = Object.entries(categoryTotals).map(([label, count]) => ({ label, count }));

  const paymentTermTotals: Record<string, number> = {};
  for (const s of suppliers) {
    const term = s.payment_terms || "Not set";
    paymentTermTotals[term] = (paymentTermTotals[term] || 0) + 1;
  }
  const paymentTermEntries = Object.entries(paymentTermTotals).sort((a, b) => b[1] - a[1]);

  const topSuppliers = suppliers
    .map((s) => ({ supplier: s, total: purchaseTotals[String(s.id)] || 0 }))
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total)
    .slice(0, 5);

  return (
    <PortalShell hospital={hospital} active="pharmacy-suppliers">
      <PageHeader
        title="Suppliers"
        description="Manage supplier profiles, contracts, contact details, and payment terms."
        actions={
          canWrite && (
            <Button
              onClick={() => {
                setEditingSupplier(null);
                setDialogOpen(true);
              }}
            >
              <Plus size={15} /> Add Supplier
            </Button>
          )
        }
      />

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Total Suppliers" value={suppliers.length} icon={Users} tint="brand" />
        <StatTile label="Active Suppliers" value={activeSuppliers.length} icon={CheckCircle2} tint="success" />
        <StatTile label="Pending Approval" value={suppliers.length - activeSuppliers.length} icon={Clock} tint="clay" />
        <StatTile label="Total Purchase Value" value={formatINR(totalPurchaseValue)} icon={Wallet} tint="brand" />
      </StatTileGrid>

      <Card className="p-space-5 mb-space-4">
        <div className="relative mb-space-4 w-72">
          <Search size={14} className="text-ink-400 absolute top-1/2 left-space-2 -translate-y-1/2" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by supplier name…" className="pl-space-6" />
        </div>
        <DataTable
          columns={createSupplierColumns((s) => {
            setEditingSupplier(s);
            setDialogOpen(true);
          })}
          data={filtered}
          getRowId={(s) => String(s.id)}
          loading={isLoading}
          emptyMessage="No suppliers added yet."
          pageSizeOptions={[10, 25, 50]}
          tableId="pharmacy-suppliers"
        />
      </Card>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <VisitTypeDonut title="Supplier Categories" data={categoryDistribution} unitLabel="suppliers" emptyMessage="No suppliers yet." />

        <Card className="p-space-4">
          <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Payment Terms Overview</p>
          {paymentTermEntries.length === 0 ? (
            <p className="text-hint py-space-4 text-center text-[12.5px]">No suppliers yet.</p>
          ) : (
            <div className="space-y-space-3">
              {paymentTermEntries.map(([term, count]) => (
                <div key={term}>
                  <div className="mb-space-1 flex items-center justify-between text-[12px]">
                    <span className="text-ink-700">{term}</span>
                    <span className="text-ink-900 font-semibold">{count} ({Math.round((100 * count) / suppliers.length)}%)</span>
                  </div>
                  <div className="bg-black/8 h-2 w-full overflow-hidden rounded-full">
                    <div className="bg-brand-600 h-full rounded-full" style={{ width: `${(100 * count) / suppliers.length}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-space-4">
          <p className="text-ink-900 mb-space-3 flex items-center gap-2 text-[13.5px] font-bold"><Trophy size={15} /> Top Suppliers (by Purchase Value)</p>
          {topSuppliers.length === 0 ? (
            <p className="text-hint py-space-4 text-center text-[12.5px]">No purchase orders yet.</p>
          ) : (
            <div className="space-y-space-2">
              {topSuppliers.map((r, i) => (
                <div key={r.supplier.id} className="flex items-center justify-between">
                  <div className="gap-space-2 flex items-center">
                    <span className="bg-brand-50 text-brand-700 flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold">{i + 1}</span>
                    <span className="text-ink-900 text-[12.5px] font-semibold">{r.supplier.name}</span>
                  </div>
                  <span className="text-ink-900 text-[12.5px] font-semibold">{formatINR(r.total)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <SupplierFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        supplier={editingSupplier}
        submitting={editingSupplier ? updating : creating}
        onSubmit={(form, is_active) =>
          editingSupplier ? updateSupplier(editingSupplier.id, form, is_active) : createSupplier(form)
        }
      />
    </PortalShell>
  );
}
