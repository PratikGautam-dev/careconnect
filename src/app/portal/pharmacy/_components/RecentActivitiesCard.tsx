"use client";

import { ClipboardList, Package, ShoppingCart, Truck } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { formatShortDateTime } from "@/lib/formatDate";
import type { PharmacyDashboard } from "@/hooks/usePharmacyDashboard";

const ICONS: Record<string, typeof ClipboardList> = {
  prescription_created: ClipboardList,
  dispensed: Package,
  stock_added: ShoppingCart,
  purchase_order: Truck,
};

export function RecentActivitiesCard({ activities }: { activities: PharmacyDashboard["recent_activities"] }) {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 text-ink-900 font-bold">Recent Activities</h3>
      {activities.length === 0 ? (
        <p className="text-hint py-space-4 text-center text-[12.5px]">No activity yet.</p>
      ) : (
        <div className="space-y-space-3">
          {activities.map((a, i) => {
            const Icon = ICONS[a.type] || ClipboardList;
            return (
              <div key={i} className="gap-space-2 flex items-start">
                <span className="bg-brand-50 text-brand-700 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full">
                  <Icon size={14} />
                </span>
                <div className="min-w-0">
                  <p className="text-ink-900 text-[12.5px]">{a.message}</p>
                  <p className="text-hint text-[11px]">{formatShortDateTime(a.at)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
