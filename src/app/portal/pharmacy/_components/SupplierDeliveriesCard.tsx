"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { formatDate } from "@/lib/formatDate";
import type { PharmacyDashboard } from "@/hooks/usePharmacyDashboard";
import { PO_STATUS_LABELS, PO_STATUS_TONES } from "../purchase-orders/_components/purchase-orders-columns";

export function SupplierDeliveriesCard({ deliveries }: { deliveries: PharmacyDashboard["supplier_deliveries"] }) {
  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-center justify-between">
        <h3 className="text-label text-ink-900 font-bold">Supplier Deliveries</h3>
        <Link href="/portal/pharmacy/purchase-orders" className="text-brand-600 text-[12px] font-semibold">View All</Link>
      </div>
      {deliveries.length === 0 ? (
        <p className="text-hint py-space-4 text-center text-[12.5px]">No purchase orders yet.</p>
      ) : (
        <div className="space-y-space-2">
          {deliveries.map((d) => (
            <div key={d.id} className="gap-space-2 flex items-center justify-between text-[13px]">
              <div className="min-w-0">
                <p className="text-ink-900 truncate font-semibold">{d.supplier_name}</p>
                <p className="text-hint text-[11px]">{formatDate(d.order_date)}</p>
              </div>
              <Badge tone={PO_STATUS_TONES[d.status as keyof typeof PO_STATUS_TONES]}>
                {PO_STATUS_LABELS[d.status as keyof typeof PO_STATUS_LABELS]}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
