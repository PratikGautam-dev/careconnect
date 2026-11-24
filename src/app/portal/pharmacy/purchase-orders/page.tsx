"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Boxes, ClipboardCheck, PackageCheck, Plus, Receipt, ShoppingCart, Truck } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { QuickActions } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { usePermission } from "@/lib/staffAuth";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import {
  usePharmacyPurchaseOrders, useRecentReceipts, type PurchaseOrder,
} from "@/hooks/usePharmacyPurchaseOrders";
import { useSupplierPerformance, usePharmacySuppliers } from "@/hooks/usePharmacySuppliers";
import { createPurchaseOrderColumns } from "./_components/purchase-orders-columns";
import { NewPurchaseOrderDialog } from "./_components/NewPurchaseOrderDialog";

type Tab = "orders" | "grn";
const TABS: { key: Tab; label: string }[] = [
  { key: "orders", label: "Purchase Orders" },
  { key: "grn", label: "GRN / Stock Receipt" },
];

export default function PurchaseOrdersPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");
  const { purchaseOrders, isLoading, createPurchaseOrder, creating } = usePharmacyPurchaseOrders(ready);
  const { medicines } = useMedicines(ready);
  const { suppliers } = usePharmacySuppliers(ready);
  const { performance } = useSupplierPerformance(ready);
  const { recentReceipts } = useRecentReceipts(ready);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("orders");

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-purchase-orders">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  const pendingOrders = purchaseOrders.filter((po) => po.status === "pending" || po.status === "in_transit");
  const receivedOrders = purchaseOrders.filter((po) => po.status === "delivered");
  const thisMonth = new Date().toISOString().slice(0, 7);
  const purchaseValueMtd = purchaseOrders
    .filter((po) => po.order_date?.slice(0, 7) === thisMonth)
    .reduce((sum, po) => sum + (po.total_amount || 0), 0);

  const grnRows: PurchaseOrder[] = purchaseOrders.filter((po) => po.delivered_at);

  return (
    <PortalShell hospital={hospital} active="pharmacy-purchase-orders">
      <PageHeader
        title="Purchase & Procurement"
        description="Create purchase orders, receive stock, and manage supplier procurement."
        actions={
          canWrite && (
            <Button onClick={() => setDialogOpen(true)}>
              <Plus size={15} /> Create PO
            </Button>
          )
        }
      />

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Purchase Orders" value={purchaseOrders.length} icon={ShoppingCart} tint="clay" />
        <StatTile label="Pending Orders" value={pendingOrders.length} icon={Truck} tint="brand" />
        <StatTile label="Orders Received" value={receivedOrders.length} icon={PackageCheck} tint="success" />
        <StatTile label="Purchase Value (MTD)" value={formatINR(purchaseValueMtd)} icon={Receipt} tint="brand" />
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
                  "px-space-4 py-space-2 rounded-full text-[13px] font-semibold transition-colors duration-150",
                  tab === t.key ? "bg-brand-600 text-white" : "bg-card border-line text-ink-600 border hover:bg-black/4",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <Card className="p-space-5">
            {tab === "orders" ? (
              <DataTable
                columns={createPurchaseOrderColumns()}
                data={purchaseOrders}
                getRowId={(po) => String(po.id)}
                loading={isLoading}
                emptyMessage="No purchase orders yet."
                pageSizeOptions={[10, 25, 50]}
                tableId="pharmacy-purchase-orders"
                onRowClick={(po) => router.push(`/portal/pharmacy/purchase-orders/${po.id}`)}
              />
            ) : (
              <DataTable
                columns={[
                  { id: "id", header: "GRN #", cell: ({ row }: { row: { original: PurchaseOrder } }) => (
                    <span className="text-brand-700 font-mono text-[12px] font-semibold">GRN-{row.original.id}</span>
                  ) },
                  { id: "supplier_name", header: "Supplier", cell: ({ row }: { row: { original: PurchaseOrder } }) => (
                    <span className="text-ink-900 font-semibold">{row.original.supplier_name}</span>
                  ) },
                  { id: "delivered_at", header: "Received On", cell: ({ row }: { row: { original: PurchaseOrder } }) => (
                    <span className="text-ink-600">{row.original.delivered_at ? formatDate(row.original.delivered_at) : "—"}</span>
                  ) },
                  { id: "total_amount", header: "Value", cell: ({ row }: { row: { original: PurchaseOrder } }) => (
                    <span className="text-ink-900">{formatINR(row.original.total_amount ?? 0)}</span>
                  ) },
                  { id: "status", header: "Status", cell: () => (
                    <Badge tone="success">Received</Badge>
                  ) },
                ]}
                data={grnRows}
                getRowId={(po: PurchaseOrder) => String(po.id)}
                emptyMessage="No stock receipts yet."
                pageSizeOptions={[10, 25, 50]}
                tableId="pharmacy-grn"
                onRowClick={(po: PurchaseOrder) => router.push(`/portal/pharmacy/purchase-orders/${po.id}`)}
              />
            )}
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Supplier Performance</p>
            {performance.length === 0 ? (
              <p className="text-hint py-space-4 text-center text-[12.5px]">No purchase orders yet.</p>
            ) : (
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-ink-400 text-left text-[10.5px] font-semibold uppercase">
                    <th className="pb-space-2">Supplier</th>
                    <th className="pb-space-2 text-right">Orders</th>
                    <th className="pb-space-2 text-right">OTD</th>
                    <th className="pb-space-2 text-right">Fill Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {performance.slice(0, 5).map((p) => (
                    <tr key={p.supplier_id} className="border-line border-t">
                      <td className="py-space-2 text-ink-900 font-semibold">{p.supplier_name}</td>
                      <td className="py-space-2 text-ink-600 text-right">{p.orders}</td>
                      <td className="py-space-2 text-right">
                        {p.otd_percent === null ? <span className="text-hint">—</span> : <Badge tone={p.otd_percent >= 90 ? "success" : "clay"}>{p.otd_percent}%</Badge>}
                      </td>
                      <td className="py-space-2 text-right">
                        {p.fill_rate_percent === null ? <span className="text-hint">—</span> : <Badge tone={p.fill_rate_percent >= 90 ? "success" : "clay"}>{p.fill_rate_percent}%</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card className="p-space-4">
            <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Recent Receipts</p>
            {recentReceipts.length === 0 ? (
              <p className="text-hint py-space-4 text-center text-[12.5px]">No receipts yet.</p>
            ) : (
              <div className="space-y-space-2">
                {recentReceipts.map((r) => (
                  <div key={r.id} className="border-line p-space-2 flex items-center justify-between rounded-md border">
                    <div>
                      <p className="text-brand-700 font-mono text-[11.5px] font-semibold">GRN-{r.id}</p>
                      <p className="text-hint text-[11px]">{r.delivered_at ? formatDate(r.delivered_at) : "—"} · {r.supplier_name}</p>
                    </div>
                    <span className="text-ink-900 text-[12px] font-semibold">{formatINR(r.total_amount ?? 0)}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {canWrite && (
            <QuickActions
              title="Quick Actions"
              columns={1}
              actions={[
                { label: "Create Purchase Order", icon: Plus, onClick: () => setDialogOpen(true) },
                { label: "Receive Stock", icon: ClipboardCheck, onClick: () => setTab("orders") },
                { label: "Check Inventory", icon: Boxes, href: "/portal/pharmacy/inventory" },
              ]}
            />
          )}
        </div>
      </div>

      <NewPurchaseOrderDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        medicines={medicines}
        suppliers={suppliers}
        onSubmit={createPurchaseOrder}
        submitting={creating}
      />
    </PortalShell>
  );
}
