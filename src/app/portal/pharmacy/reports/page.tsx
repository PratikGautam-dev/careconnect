"use client";

import { useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDown, ArrowUp, Boxes, ClipboardList, Package, PackageOpen, RefreshCw, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { formatDate } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { usePharmacyReports } from "@/hooks/usePharmacyReports";
import { VisitTypeDonut } from "../../report-analytics/_components/VisitTypeDonut";

const RANGE_OPTIONS = [
  { value: 7, label: "Last 7 Days" },
  { value: 30, label: "Last 30 Days" },
  { value: 90, label: "Last 90 Days" },
];

export default function PharmacyReportsPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const [days, setDays] = useState(30);
  const { reports, isLoading } = usePharmacyReports(ready, days);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-reports">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-reports">
      <PageHeader
        title="Reports & Analytics"
        description="Explore pharmacy performance, sales, stock, and procurement insights."
        actions={
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border-line bg-card px-space-3 text-ink-900 h-10 rounded-md border text-[13px]"
          >
            {RANGE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        }
      />

      <StatTileGrid cols={4} className="mb-space-4">
        <StatTile label="Total Sales" value={formatINR(reports?.total_sales ?? 0)} icon={Wallet} tint="brand" />
        <StatTile label="Prescriptions Dispensed" value={reports?.prescriptions_dispensed ?? 0} icon={ClipboardList} tint="clay" />
        <StatTile label="Items Sold" value={reports?.items_sold ?? 0} icon={Package} tint="success" />
        <StatTile label="Inventory Value" value={formatINR(reports?.inventory_value ?? 0)} icon={Boxes} tint="brand" />
      </StatTileGrid>

      <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-3">
        <Card className="p-space-4 lg:col-span-2">
          <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Sales Trend</p>
          {!isLoading && (reports?.sales_trend.length ?? 0) === 0 ? (
            <p className="text-hint py-space-6 text-center text-[12.5px]">No sales in this period.</p>
          ) : (
            <div style={{ width: "100%", height: 260 }}>
              <ResponsiveContainer>
                <AreaChart data={reports?.sales_trend ?? []}>
                  <defs>
                    <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#1baf7a" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#1baf7a" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tickFormatter={(d) => formatDate(d)} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatINR(v)} width={70} />
                  <Tooltip formatter={(v: number) => formatINR(v)} labelFormatter={(d) => formatDate(String(d))} />
                  <Area type="monotone" dataKey="amount" stroke="#1baf7a" fill="url(#salesFill)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <VisitTypeDonut title="Sales by Category" data={reports?.sales_by_category ?? []} unitLabel="₹" emptyMessage="No sales yet." />
      </div>

      <div className="gap-space-4 mb-space-4 grid grid-cols-1 lg:grid-cols-2">
        <Card className="p-space-4">
          <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Top Selling Medicines</p>
          {(reports?.top_selling_medicines.length ?? 0) === 0 ? (
            <p className="text-hint py-space-4 text-center text-[12.5px]">No sales yet.</p>
          ) : (
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-ink-400 text-left text-[11px] font-semibold uppercase">
                  <th className="pb-space-2">Medicine</th>
                  <th className="pb-space-2 text-right">Items Sold</th>
                  <th className="pb-space-2 text-right">Sales</th>
                </tr>
              </thead>
              <tbody>
                {reports?.top_selling_medicines.map((m) => (
                  <tr key={m.medicine_id} className="border-line border-t">
                    <td className="py-space-2 text-ink-900 font-semibold">{m.medicine_name}</td>
                    <td className="py-space-2 text-ink-600 text-right">{m.items_sold}</td>
                    <td className="py-space-2 text-ink-900 text-right">{formatINR(m.sales_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="p-space-4">
          <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Stock Movement Summary</p>
          <div className="gap-space-3 grid grid-cols-2">
            <div className="bg-success-tint p-space-3 rounded-md">
              <p className="text-ink-600 flex items-center gap-1 text-[11.5px]"><ArrowUp size={13} className="text-success" /> Stock In</p>
              <p className="text-ink-900 text-[20px] font-bold">{reports?.stock_movement.stock_in ?? 0}</p>
            </div>
            <div className="bg-error-tint p-space-3 rounded-md">
              <p className="text-ink-600 flex items-center gap-1 text-[11.5px]"><ArrowDown size={13} className="text-error" /> Stock Out</p>
              <p className="text-ink-900 text-[20px] font-bold">{reports?.stock_movement.stock_out ?? 0}</p>
            </div>
            <div className="bg-brand-50 p-space-3 rounded-md">
              <p className="text-ink-600 flex items-center gap-1 text-[11.5px]"><RefreshCw size={13} className="text-brand-600" /> Net Movement</p>
              <p className="text-ink-900 text-[20px] font-bold">{reports?.stock_movement.net_movement ?? 0}</p>
            </div>
            <div className="bg-clay-100 p-space-3 rounded-md">
              <p className="text-ink-600 flex items-center gap-1 text-[11.5px]"><PackageOpen size={13} className="text-clay-700" /> Low Stock Items</p>
              <p className="text-ink-900 text-[20px] font-bold">{reports?.stock_movement.low_stock_items ?? 0}</p>
            </div>
          </div>
        </Card>
      </div>

      <Card className="p-space-4">
        <p className="text-ink-900 mb-space-3 text-[13.5px] font-bold">Procurement Summary</p>
        {(reports?.procurement_summary.length ?? 0) === 0 ? (
          <p className="text-hint py-space-4 text-center text-[12.5px]">No purchase orders yet.</p>
        ) : (
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="text-ink-400 text-left text-[11px] font-semibold uppercase">
                <th className="pb-space-2">Supplier</th>
                <th className="pb-space-2">Order Date</th>
                <th className="pb-space-2 pr-space-4 text-right">Amount</th>
                <th className="pb-space-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {reports?.procurement_summary.map((po) => (
                <tr key={po.id} className="border-line border-t">
                  <td className="py-space-2 text-ink-900 font-semibold">{po.supplier_name || "—"}</td>
                  <td className="py-space-2 text-ink-600">{formatDate(po.order_date)}</td>
                  <td className="py-space-2 pr-space-4 text-ink-900 text-right">{formatINR(po.total_amount ?? 0)}</td>
                  <td className="py-space-2"><Badge tone="clay">{po.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </PortalShell>
  );
}
