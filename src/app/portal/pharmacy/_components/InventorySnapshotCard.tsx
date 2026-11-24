"use client";

import { VisitTypeDonut } from "@/app/portal/report-analytics/_components/VisitTypeDonut";
import type { PharmacyDashboard } from "@/hooks/usePharmacyDashboard";

export function InventorySnapshotCard({ snapshot }: { snapshot: PharmacyDashboard["inventory_snapshot"] }) {
  return (
    <VisitTypeDonut
      title="Inventory Snapshot"
      data={snapshot.breakdown}
      unitLabel="items"
      emptyMessage="No medicines in the catalog yet."
      className="h-full"
    />
  );
}
