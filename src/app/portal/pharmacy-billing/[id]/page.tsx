"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Printer } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { usePermission } from "@/lib/staffAuth";
import { fetchPharmacySale, usePharmacyBilling } from "@/hooks/usePharmacyBilling";
import { CollectPaymentDialog } from "../_components/CollectPaymentDialog";
import { SALE_STATUS_LABELS, SALE_STATUS_TONES } from "../_components/pharmacy-sales-columns";

export default function PharmacySaleDetailPage() {
  const params = useParams<{ id: string }>();
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy_billing", "write");
  const { collectPayment, collecting } = usePharmacyBilling(false);
  const queryClient = useQueryClient();
  const queryKey = ["portal-pharmacy-sale", params.id];
  const { data: sale, isLoading: loading } = useQuery({
    queryKey,
    enabled: ready,
    retry: false,
    queryFn: () => fetchPharmacySale(Number(params.id)),
  });
  const [dialogOpen, setDialogOpen] = useState(false);

  function load() {
    queryClient.invalidateQueries({ queryKey });
  }

  if (!hospital) return null;

  return (
    <PortalShell hospital={hospital} active="pharmacy-billing">
      <PageHeader
        title={sale ? sale.sale_number : "Pharmacy Sale"}
        actions={
          <div className="gap-space-2 flex">
            <Button href="/portal/pharmacy-billing" variant="ghost">
              <ChevronLeft size={15} /> Back to Pharmacy Billing
            </Button>
            {sale && (
              <Button variant="secondary" onClick={() => window.print()}>
                <Printer size={15} /> Print Invoice
              </Button>
            )}
          </div>
        }
      />
      {loading && <p className="text-hint text-[13px]">Loading…</p>}
      {!loading && !sale && <p className="text-hint text-[13px]">No such sale.</p>}
      {sale && (
        <div className="space-y-space-4">
          <Card className="p-space-5">
            <div className="gap-space-4 grid grid-cols-2 sm:grid-cols-4">
              <div>
                <p className="text-hint text-[11.5px]">Patient</p>
                <p className="text-ink-900 font-semibold">{sale.patient_name || "Walk-in"}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Date</p>
                <p className="text-ink-900 font-semibold">{formatShortDateTime(sale.created_at)}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Total</p>
                <p className="text-ink-900 font-semibold">{formatINR(sale.total_amount)}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Status</p>
                <Badge tone={SALE_STATUS_TONES[sale.payment_status]}>{SALE_STATUS_LABELS[sale.payment_status]}</Badge>
              </div>
            </div>
            {sale.payment_method && (
              <p className="text-hint mt-space-3 text-[12.5px]">
                Paid via {sale.payment_method.replace("_", " ")} -- {sale.payment_amount != null ? formatINR(sale.payment_amount) : ""}
              </p>
            )}
          </Card>

          <Card className="p-space-5">
            <p className="text-ink-900 mb-space-3 text-[15px] font-semibold">Items</p>
            <div className="space-y-space-2">
              {sale.items.map((item) => (
                <div key={item.id} className="border-line py-space-2 flex items-center justify-between border-b text-[13.5px] last:border-b-0">
                  <div>
                    <p className="text-ink-900 font-semibold">{item.medicine_name}</p>
                    <p className="text-hint text-[11.5px]">Batch {item.batch_number} · Qty {item.quantity} x {formatINR(item.unit_price)}</p>
                  </div>
                  <p className="text-ink-900 font-semibold">{formatINR(item.line_total)}</p>
                </div>
              ))}
            </div>
            <div className="border-line mt-space-3 pt-space-3 flex items-center justify-between border-t">
              <p className="text-ink-900 font-bold">Total</p>
              <p className="text-ink-900 font-bold">{formatINR(sale.total_amount)}</p>
            </div>
            {canWrite && sale.payment_status === "pending" && (
              <Button onClick={() => setDialogOpen(true)} className="mt-space-4">
                Collect Payment
              </Button>
            )}
          </Card>
        </div>
      )}

      <CollectPaymentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        sale={sale ?? null}
        submitting={collecting}
        onSubmit={async (method, amount) => {
          await collectPayment(sale!.id, method, amount);
          load();
        }}
      />
    </PortalShell>
  );
}
