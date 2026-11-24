"use client";

import { useState } from "react";
import { BedDouble, ClipboardCheck, PackageCheck, Pill, Truck } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { QuickActions } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePermission } from "@/lib/staffAuth";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { usePharmacyDashboard } from "@/hooks/usePharmacyDashboard";
import { usePharmacyPrescriptions } from "@/hooks/usePharmacyPrescriptions";
import { usePharmacySuppliers } from "@/hooks/usePharmacySuppliers";
import { AddStockDialog } from "./inventory/_components/AddStockDialog";
import { usePharmacyInventory } from "@/hooks/usePharmacyInventory";
import { NewPurchaseOrderDialog } from "./purchase-orders/_components/NewPurchaseOrderDialog";
import { usePharmacyPurchaseOrders } from "@/hooks/usePharmacyPurchaseOrders";
import { InventorySnapshotCard } from "./_components/InventorySnapshotCard";
import { LowStockExpiryAlertsCard } from "./_components/LowStockExpiryAlertsCard";
import { PrescriptionQueueCard } from "./_components/PrescriptionQueueCard";
import { RecentActivitiesCard } from "./_components/RecentActivitiesCard";
import { SupplierDeliveriesCard } from "./_components/SupplierDeliveriesCard";
import { TopSellingMedicinesCard } from "./_components/TopSellingMedicinesCard";

export default function PharmacyDashboardPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const canWrite = usePermission("pharmacy", "write");
  const { dashboard, isLoading } = usePharmacyDashboard(ready);
  const { prescriptions } = usePharmacyPrescriptions(ready);
  const { medicines } = useMedicines(ready);
  const { suppliers } = usePharmacySuppliers(ready);
  const { addStock, addingStock } = usePharmacyInventory(ready);
  const { createPurchaseOrder, creating: creatingPO } = usePharmacyPurchaseOrders(ready);

  const [addStockOpen, setAddStockOpen] = useState(false);
  const [newPoOpen, setNewPoOpen] = useState(false);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-dashboard">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-dashboard">
      <PageHeader title="Pharmacy Portal Dashboard" description="Safe Medicines. Better Care. Always." />

      {isLoading && <p className="text-hint mb-space-4 text-[13px]">Loading…</p>}

      {dashboard && (
        <>
          <StatTileGrid cols={5} className="mb-space-4">
            <StatTile label="Prescriptions Today" value={dashboard.stats.prescriptions_today.value} icon={ClipboardCheck} tint="brand" delta={dashboard.stats.prescriptions_today.delta} />
            <StatTile label="Medicines Dispensed" value={dashboard.stats.medicines_dispensed_today.value} icon={PackageCheck} tint="success" delta={dashboard.stats.medicines_dispensed_today.delta} />
            <StatTile label="Low Stock Items" value={dashboard.stats.low_stock_items.value} icon={Pill} tint="error" delta={dashboard.stats.low_stock_items.delta} />
            <StatTile label="Near-Expiry Items" value={dashboard.stats.near_expiry_items.value} icon={BedDouble} tint="clay" delta={dashboard.stats.near_expiry_items.delta} />
            <StatTile label="Pending Orders" value={dashboard.stats.pending_orders.value} icon={Truck} tint="brand" href="/portal/pharmacy/purchase-orders" delta={dashboard.stats.pending_orders.delta} />
          </StatTileGrid>

          <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-3">
            <PrescriptionQueueCard prescriptions={prescriptions} />
            <InventorySnapshotCard snapshot={dashboard.inventory_snapshot} />
            <LowStockExpiryAlertsCard lowStock={dashboard.low_stock} nearExpiry={dashboard.near_expiry} />
          </div>

          <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-3">
            <TopSellingMedicinesCard items={dashboard.top_selling_medicines} />
            <SupplierDeliveriesCard deliveries={dashboard.supplier_deliveries} />
            <RecentActivitiesCard activities={dashboard.recent_activities} />
          </div>

          {canWrite && (
            <QuickActions
              title="Quick Actions"
              columns={2}
              actions={[
                { label: "Dispense Medicine", icon: Pill, href: "/portal/pharmacy/prescriptions" },
                { label: "Add Stock", icon: PackageCheck, onClick: () => setAddStockOpen(true) },
                { label: "Raise Purchase Order", icon: Truck, onClick: () => setNewPoOpen(true) },
                { label: "Print Invoice", icon: ClipboardCheck, href: "/portal/pharmacy-billing" },
              ]}
            />
          )}
        </>
      )}

      <AddStockDialog open={addStockOpen} onOpenChange={setAddStockOpen} medicines={medicines} suppliers={suppliers} onSubmit={addStock} submitting={addingStock} />
      <NewPurchaseOrderDialog open={newPoOpen} onOpenChange={setNewPoOpen} medicines={medicines} suppliers={suppliers} onSubmit={createPurchaseOrder} submitting={creatingPO} />
    </PortalShell>
  );
}
