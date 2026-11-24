"use client";

import { Card } from "@/components/ui/Card";
import type { PharmacyDashboard } from "@/hooks/usePharmacyDashboard";

export function TopSellingMedicinesCard({ items }: { items: PharmacyDashboard["top_selling_medicines"] }) {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 text-ink-900 font-bold">Top-Selling Medicines <span className="text-hint font-normal">(this month)</span></h3>
      {items.length === 0 ? (
        <p className="text-hint py-space-4 text-center text-[12.5px]">No sales yet this month.</p>
      ) : (
        <div className="space-y-space-2">
          {items.map((item, i) => (
            <div key={item.medicine_id} className="gap-space-2 flex items-center">
              <span className="bg-brand-50 text-brand-700 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold">
                {i + 1}
              </span>
              <p className="text-ink-900 flex-1 truncate text-[13px] font-medium">{item.name}</p>
              <p className="text-ink-600 text-[12.5px] font-semibold">{item.units_dispensed} units</p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
