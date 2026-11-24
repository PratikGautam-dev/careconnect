"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import type { PharmacyDashboard } from "@/hooks/usePharmacyDashboard";

type Props = {
  lowStock: PharmacyDashboard["low_stock"];
  nearExpiry: PharmacyDashboard["near_expiry"];
};

export function LowStockExpiryAlertsCard({ lowStock, nearExpiry }: Props) {
  const [tab, setTab] = useState<"low_stock" | "near_expiry">("low_stock");

  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 text-ink-900 font-bold">Low Stock & Expiry Alerts</h3>
      <div className="gap-space-2 mb-space-3 flex">
        <button
          type="button"
          onClick={() => setTab("low_stock")}
          className={cn(
            "px-space-3 py-space-1 rounded-full text-[12px] font-semibold transition-colors duration-150",
            tab === "low_stock" ? "bg-brand-600 text-white" : "bg-black/4 text-ink-600 hover:bg-black/6",
          )}
        >
          Low Stock ({lowStock.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("near_expiry")}
          className={cn(
            "px-space-3 py-space-1 rounded-full text-[12px] font-semibold transition-colors duration-150",
            tab === "near_expiry" ? "bg-brand-600 text-white" : "bg-black/4 text-ink-600 hover:bg-black/6",
          )}
        >
          Near Expiry ({nearExpiry.length})
        </button>
      </div>
      <div className="space-y-space-2 max-h-72 overflow-y-auto">
        {tab === "low_stock" &&
          (lowStock.length === 0 ? (
            <p className="text-hint py-space-4 text-center text-[12.5px]">Nothing low on stock.</p>
          ) : (
            lowStock.map((m) => (
              <div key={m.id} className="bg-error-tint px-space-3 py-space-2 flex items-center justify-between rounded-md">
                <div>
                  <p className="text-ink-900 text-[13px] font-semibold">{m.name}</p>
                  <p className="text-hint text-[11px]">Stock: {m.quantity_on_hand} (reorder at {m.reorder_level})</p>
                </div>
                <span className="text-error px-space-2 py-0.5 rounded-full bg-white text-[10.5px] font-bold uppercase">Low Stock</span>
              </div>
            ))
          ))}
        {tab === "near_expiry" &&
          (nearExpiry.length === 0 ? (
            <p className="text-hint py-space-4 text-center text-[12.5px]">Nothing expiring soon.</p>
          ) : (
            nearExpiry.map((b) => (
              <div key={b.id} className="bg-clay-100 px-space-3 py-space-2 flex items-center justify-between rounded-md">
                <div>
                  <p className="text-ink-900 text-[13px] font-semibold">{b.medicine_name}</p>
                  <p className="text-hint text-[11px]">Batch {b.batch_number} · {b.quantity_on_hand} units · expires {formatDate(b.expiry_date)}</p>
                </div>
                <span className="text-clay-700 px-space-2 py-0.5 rounded-full bg-white text-[10.5px] font-bold uppercase">Expiring Soon</span>
              </div>
            ))
          ))}
      </div>
    </Card>
  );
}
