"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  AlertTriangle, Eye, FileText, IndianRupee, MoreHorizontal, Package, Plus, Receipt, Search, Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { usePermission } from "@/lib/staffAuth";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import {
  usePharmacyBilling, usePharmacyBillingStats, type PharmacySale, type SaleType,
} from "@/hooks/usePharmacyBilling";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import {
  SALE_STATUS_LABELS, SALE_STATUS_TONES, SALE_TYPE_LABELS, SALE_TYPE_TONES,
} from "./_components/pharmacy-sales-columns";
import { NewOtcSaleDialog } from "./_components/NewOtcSaleDialog";
import { CollectPaymentDialog } from "./_components/CollectPaymentDialog";
import { CollectionDonut } from "./_components/CollectionDonut";

const TABS: { key: SaleType; label: string; icon: typeof FileText }[] = [
  { key: "prescription", label: "Prescription Bills", icon: FileText },
  { key: "otc", label: "OTC Sales", icon: Package },
  { key: "ipd", label: "IPD Bills", icon: Receipt },
];

function pctLabel(pct: number | null): { value: string; direction: "up" | "down" } | null {
  if (pct === null) return null;
  return { value: `${Math.abs(pct)}%`, direction: pct >= 0 ? "up" : "down" };
}

export default function PharmacyBillingPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy_billing", "view");
  const canWrite = usePermission("pharmacy_billing", "write");
  const [tab, setTab] = useState<SaleType>("prescription");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const { sales, total, isLoading, createOtcSale, creatingOtcSale, collectPayment, collecting } = usePharmacyBilling(ready, undefined, page, tab, search);
  const { stats } = usePharmacyBillingStats(ready);
  const { medicines } = useMedicines(ready);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [collectSale, setCollectSale] = useState<PharmacySale | null>(null);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-billing">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  // Recent Transactions -- last 4 bills from whatever's currently loaded
  // (still scoped by the active tab/search, same as `sales` itself -- there's
  // no separate "every type, unfiltered" fetch backing this card).
  const recent = [...sales].sort((a, b) => b.id - a.id).slice(0, 4);

  return (
    <PortalShell hospital={hospital} active="pharmacy-billing">
      <PageHeader
        title="Sales & Billing"
        description="Create bills for prescriptions, OTC sales and inpatient (IPD) orders."
      />

      <StatTileGrid cols={5} className="mb-space-4">
        <StatTile label="Today's Sales" value={stats?.today_sales ?? null} icon={IndianRupee} prefix="₹" delta={pctLabel(stats?.today_sales_change_pct ?? null)} />
        <StatTile label="Bills Generated" value={stats?.bills_generated ?? null} icon={FileText} tint="clay" delta={pctLabel(stats?.bills_generated_change_pct ?? null)} />
        <StatTile label="Avg. Bill Value" value={stats?.avg_bill_value ?? null} icon={Wallet} prefix="₹" delta={pctLabel(stats?.avg_bill_value_change_pct ?? null)} />
        <StatTile label="Outstanding Amount" value={stats?.outstanding_amount ?? null} icon={AlertTriangle} prefix="₹" tint="error" />
        <StatTile label="Payment Collection" value={stats?.payment_collection_today ?? null} icon={Wallet} prefix="₹" tint="success" delta={pctLabel(stats?.payment_collection_change_pct ?? null)} />
      </StatTileGrid>

      <Card className="p-space-4">
        <div className="mb-space-3 gap-space-2 flex flex-wrap items-center justify-between">
          <div className="gap-space-2 flex flex-wrap">
            {TABS.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => { setTab(t.key); setPage(1); }}
                  className={cn(
                    "gap-space-2 px-space-4 py-space-2 flex items-center rounded-md text-[13px] font-semibold transition-colors duration-150",
                    tab === t.key ? "bg-brand-600 text-white" : "bg-card border-line text-ink-600 border hover:bg-black/4",
                  )}
                >
                  <Icon size={15} /> {t.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mb-space-4 gap-space-2 flex flex-wrap items-center justify-between">
          <div className="relative min-w-50 flex-1">
            <Search size={14} className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2" />
            <input
              type="text" placeholder="Search by Bill No., Patient, Prescription ID…"
              value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-10 w-full rounded-md border text-[13px] outline-none"
            />
          </div>
          {canWrite && (
            <Button onClick={() => setDialogOpen(true)}>
              <Plus size={15} /> New Bill
            </Button>
          )}
        </div>

        <DataTable
          columns={[
            { id: "sale_number", header: "Bill No.", cell: ({ row }: { row: { original: PharmacySale } }) => (
              <button type="button" onClick={() => router.push(`/portal/pharmacy-billing/${row.original.id}`)} className="text-brand-700 font-mono text-[12px] font-semibold hover:underline">
                {row.original.sale_number}
              </button>
            ) },
            { id: "sale_type", header: "Type", cell: ({ row }: { row: { original: PharmacySale } }) => <Badge tone={SALE_TYPE_TONES[row.original.sale_type]}>{SALE_TYPE_LABELS[row.original.sale_type]}</Badge> },
            { id: "patient_name", header: "Patient", cell: ({ row }: { row: { original: PharmacySale } }) => (
              <div>
                <p className="text-ink-900 font-semibold">{row.original.patient_name || "Walk-in"}</p>
                {row.original.patient_mrn && <p className="text-hint text-[11px]">{row.original.patient_mrn}</p>}
              </div>
            ) },
            { id: "prescription_id", header: "Prescription ID", cell: ({ row }: { row: { original: PharmacySale } }) => (
              row.original.prescription_id
                ? <span className="text-brand-700 font-mono text-[12px] font-semibold">RX-{row.original.prescription_id}</span>
                : <span className="text-ink-400">—</span>
            ) },
            { id: "total_amount", header: "Amount", cell: ({ row }: { row: { original: PharmacySale } }) => <span className="text-ink-900 font-semibold">{formatINR(row.original.total_amount)}</span> },
            { id: "payment_status", header: "Payment Status", cell: ({ row }: { row: { original: PharmacySale } }) => <Badge tone={SALE_STATUS_TONES[row.original.payment_status]}>{SALE_STATUS_LABELS[row.original.payment_status]}</Badge> },
            { id: "created_at", header: "Date & Time", cell: ({ row }: { row: { original: PharmacySale } }) => <span className="text-ink-600">{formatShortDateTime(row.original.created_at)}</span> },
            { id: "actions", header: "Actions", enableHiding: false, cell: ({ row }: { row: { original: PharmacySale } }) => {
              const s = row.original;
              const unpaid = s.payment_status === "pending" || s.payment_status === "partially_paid";
              return (
                <div className="gap-space-1 flex items-center" onClick={(e) => e.stopPropagation()}>
                  <Button size="md" variant="secondary" onClick={() => router.push(`/portal/pharmacy-billing/${s.id}`)}>
                    <Eye size={13} /> View
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger className="text-ink-600 hover:text-ink-900 inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-black/4" aria-label={`More actions for ${s.sale_number}`}>
                      <MoreHorizontal size={16} />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem onClick={() => router.push(`/portal/pharmacy-billing/${s.id}`)}>
                        <Eye size={14} /> View Invoice
                      </DropdownMenuItem>
                      {canWrite && unpaid && (
                        <DropdownMenuItem onClick={() => setCollectSale(s)}>
                          <Wallet size={14} /> Collect Payment
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              );
            } },
          ]}
          data={sales}
          getRowId={(s: PharmacySale) => String(s.id)}
          loading={isLoading}
          emptyMessage="No bills in this category yet."
          onRowClick={(s: PharmacySale) => router.push(`/portal/pharmacy-billing/${s.id}`)}
          pagination={{ page, limit: 20, total }}
          onPageChange={setPage}
        />
      </Card>

      <div className="mt-space-4 gap-space-4 grid grid-cols-1 lg:grid-cols-2">
        <Card className="p-space-4">
          <div className="mb-space-3 flex items-center justify-between">
            <h3 className="text-label text-ink-900 font-bold">Recent Transactions</h3>
            <button type="button" onClick={() => { setTab("prescription"); setSearch(""); setPage(1); }} className="text-brand-700 text-[12.5px] font-semibold hover:underline">
              View All →
            </button>
          </div>
          {recent.length === 0 ? (
            <p className="text-hint py-space-4 text-center text-[12.5px]">No transactions yet.</p>
          ) : (
            <div className="divide-line divide-y">
              {recent.map((s) => (
                <button
                  key={s.id} type="button" onClick={() => router.push(`/portal/pharmacy-billing/${s.id}`)}
                  className="py-space-2 flex w-full items-center justify-between text-left"
                >
                  <div>
                    <p className="text-brand-700 font-mono text-[12px] font-semibold">{s.sale_number}</p>
                    <p className="text-hint text-[11.5px]">{s.patient_name || "Walk-in"} ({SALE_TYPE_LABELS[s.sale_type]})</p>
                  </div>
                  <div className="text-right">
                    <p className="text-ink-900 text-[12.5px] font-semibold">{formatINR(s.total_amount)}</p>
                    <Badge tone={SALE_STATUS_TONES[s.payment_status]}>{SALE_STATUS_LABELS[s.payment_status]}</Badge>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>

        <CollectionDonut
          billedToday={stats?.billed_today_by_status ?? { paid: 0, partially_paid: 0, pending: 0 }}
          outstandingAmount={stats?.outstanding_amount ?? 0}
        />
      </div>

      <NewOtcSaleDialog open={dialogOpen} onOpenChange={setDialogOpen} medicines={medicines} submitting={creatingOtcSale} onSubmit={createOtcSale} />
      <CollectPaymentDialog
        open={!!collectSale} onOpenChange={(open) => !open && setCollectSale(null)} sale={collectSale}
        submitting={collecting}
        onSubmit={async (method, amount) => { if (collectSale) { await collectPayment(collectSale.id, method, amount); setCollectSale(null); } }}
      />
    </PortalShell>
  );
}
