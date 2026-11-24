"use client";

import { useState } from "react";
import { AlertTriangle, Boxes, Calendar, CircleOff, Search } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { QuickActions } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/formatDate";
import { usePermission } from "@/lib/staffAuth";
import { usePharmacyInventory } from "@/hooks/usePharmacyInventory";
import { useNearExpiryBatches } from "@/hooks/useStockAlerts";

type Tab = "low_stock" | "near_expiry" | "out_of_stock";
const TABS: { key: Tab; label: string }[] = [
  { key: "low_stock", label: "Low Stock" },
  { key: "near_expiry", label: "Near Expiry" },
  { key: "out_of_stock", label: "Out of Stock" },
];

type AlertRow = {
  key: string;
  medicine_name: string;
  category: string | null;
  current_stock: number;
  reorder_level: number | null;
  alert_type: "low_stock" | "near_expiry" | "out_of_stock";
  expiry: string | null;
};

export default function StockAlertsPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const { inventory } = usePharmacyInventory(ready);
  const { nearExpiryBatches } = useNearExpiryBatches(ready);

  const [tab, setTab] = useState<Tab>("low_stock");
  const [search, setSearch] = useState("");

  const lowStock: AlertRow[] = inventory
    .filter((m) => m.quantity_on_hand > 0 && m.quantity_on_hand < m.reorder_level)
    .map((m) => ({
      key: `low-${m.id}`, medicine_name: m.name, category: m.category,
      current_stock: m.quantity_on_hand, reorder_level: m.reorder_level,
      alert_type: "low_stock", expiry: m.nearest_expiry_date,
    }));
  const outOfStock: AlertRow[] = inventory
    .filter((m) => m.quantity_on_hand === 0)
    .map((m) => ({
      key: `oos-${m.id}`, medicine_name: m.name, category: m.category,
      current_stock: 0, reorder_level: m.reorder_level,
      alert_type: "out_of_stock", expiry: null,
    }));
  const nearExpiry: AlertRow[] = nearExpiryBatches.map((b) => ({
    key: `exp-${b.id}`, medicine_name: b.medicine_name, category: null,
    current_stock: b.quantity_on_hand, reorder_level: null,
    alert_type: "near_expiry", expiry: b.expiry_date,
  }));

  const rowsByTab: Record<Tab, AlertRow[]> = { low_stock: lowStock, near_expiry: nearExpiry, out_of_stock: outOfStock };
  const totalAlerts = lowStock.length + nearExpiry.length + outOfStock.length;

  const activeRows = rowsByTab[tab];
  const filtered = search.trim()
    ? activeRows.filter((r) => r.medicine_name.toLowerCase().includes(search.trim().toLowerCase()))
    : activeRows;

  const topCritical = [...outOfStock, ...lowStock].slice(0, 3);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-alerts">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-alerts">
      <PageHeader title="Stock Alerts" description="Monitor low stock, near expiry and out-of-stock medicines." />

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Low Stock Items" value={lowStock.length} icon={AlertTriangle} tint="clay" />
        <StatTile label="Near Expiry Items" value={nearExpiry.length} icon={Calendar} tint="brand" />
        <StatTile label="Out of Stock Items" value={outOfStock.length} icon={CircleOff} tint="error" />
        <StatTile label="Total Alert Items" value={totalAlerts} icon={Boxes} tint="success" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-space-3">
          <div className="gap-space-2 flex flex-wrap items-center justify-between">
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
            <div className="relative w-56">
              <Search size={14} className="text-ink-400 absolute top-1/2 left-space-2 -translate-y-1/2" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search medicine…" className="pl-space-6" />
            </div>
          </div>

          <Card className="p-space-4">
            <DataTable
              columns={[
                { id: "medicine_name", header: "Medicine", cell: ({ row }: { row: { original: AlertRow } }) => (
                  <span className="text-ink-900 font-semibold">{row.original.medicine_name}</span>
                ) },
                { id: "category", header: "Category", cell: ({ row }: { row: { original: AlertRow } }) => (
                  <span className="text-ink-600">{row.original.category || "—"}</span>
                ) },
                { id: "current_stock", header: "Current Stock", cell: ({ row }: { row: { original: AlertRow } }) => (
                  <span className={row.original.current_stock === 0 ? "text-error font-semibold" : "text-ink-900 font-semibold"}>{row.original.current_stock}</span>
                ) },
                { id: "reorder_level", header: "Reorder Level", cell: ({ row }: { row: { original: AlertRow } }) => (
                  <span className="text-ink-600">{row.original.reorder_level ?? "—"}</span>
                ) },
                { id: "expiry", header: "Expiry", cell: ({ row }: { row: { original: AlertRow } }) => (
                  <span className="text-ink-600">{row.original.expiry ? formatDate(row.original.expiry) : "—"}</span>
                ) },
                { id: "alert_type", header: "Alert Type", cell: ({ row }: { row: { original: AlertRow } }) => (
                  <Badge tone={row.original.alert_type === "out_of_stock" ? "neutral" : row.original.alert_type === "near_expiry" ? "brand" : "clay"}>
                    {row.original.alert_type === "out_of_stock" ? "Out of Stock" : row.original.alert_type === "near_expiry" ? "Near Expiry" : "Low Stock"}
                  </Badge>
                ) },
              ]}
              data={filtered}
              getRowId={(r: AlertRow) => r.key}
              emptyMessage="Nothing in this category."
              pageSizeOptions={[10, 25, 50]}
              tableId="pharmacy-stock-alerts"
            />
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Top Critical Items</p>
            {topCritical.length === 0 ? (
              <p className="text-hint py-space-4 text-center text-[12.5px]">Nothing critical right now.</p>
            ) : (
              <div className="space-y-space-2">
                {topCritical.map((item) => (
                  <div key={item.key} className="border-line p-space-2 flex items-center justify-between rounded-md border">
                    <div>
                      <p className="text-ink-900 text-[12.5px] font-semibold">{item.medicine_name}</p>
                      <p className="text-hint text-[11px]">{item.current_stock} units</p>
                    </div>
                    <Badge tone={item.alert_type === "out_of_stock" ? "neutral" : "clay"}>
                      {item.alert_type === "out_of_stock" ? "Out of Stock" : "Low Stock"}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <QuickActions
            title="Quick Actions"
            columns={2}
            actions={[
              { label: "Create PO", icon: Boxes, href: "/portal/pharmacy/purchase-orders" },
              { label: "View Inventory", icon: Boxes, href: "/portal/pharmacy/inventory" },
            ]}
          />
        </div>
      </div>
    </PortalShell>
  );
}
