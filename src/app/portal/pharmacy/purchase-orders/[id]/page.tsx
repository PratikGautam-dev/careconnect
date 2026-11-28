"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatDate } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { toast } from "@/lib/toast";
import { usePermission } from "@/lib/staffAuth";
import { fetchPurchaseOrder, receivePurchaseOrderDelivery } from "@/hooks/usePharmacyPurchaseOrders";
import { PO_STATUS_LABELS, PO_STATUS_TONES } from "../_components/purchase-orders-columns";

type ReceiveRow = { batch_number: string; expiry_date: string; quantity_received: string };

export default function PurchaseOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { hospital, ready } = usePortalGuard();
  const canWrite = usePermission("pharmacy", "write");
  const queryClient = useQueryClient();
  const queryKey = ["portal-pharmacy-purchase-order", params.id];
  const { data: po, isLoading: loading } = useQuery({
    queryKey,
    enabled: ready,
    retry: false,
    queryFn: () => fetchPurchaseOrder(Number(params.id)),
  });
  const [receiveRows, setReceiveRows] = useState<Record<number, ReceiveRow>>({});
  const [submitting, setSubmitting] = useState(false);

  function load() {
    queryClient.invalidateQueries({ queryKey });
  }

  if (!hospital) return null;

  function updateRow(itemId: number, patch: Partial<ReceiveRow>) {
    const defaults: ReceiveRow = { batch_number: "", expiry_date: "", quantity_received: "" };
    setReceiveRows((rows) => ({
      ...rows,
      [itemId]: { ...defaults, ...rows[itemId], ...patch },
    }));
  }

  async function handleReceive() {
    if (!po) return;
    const itemBatches = Object.entries(receiveRows)
      .filter(([, row]) => row.batch_number && row.expiry_date && row.quantity_received)
      .map(([itemId, row]) => ({
        purchase_order_item_id: Number(itemId),
        batch_number: row.batch_number,
        expiry_date: row.expiry_date,
        quantity_received: Number(row.quantity_received),
      }));
    if (itemBatches.length === 0) {
      toast.error("Nothing to receive", "Fill in batch number, expiry, and quantity for at least one item.");
      return;
    }
    setSubmitting(true);
    const result = await receivePurchaseOrderDelivery(po.id, itemBatches);
    setSubmitting(false);
    if (!result.ok) {
      toast.error("Couldn't receive delivery", result.error);
      return;
    }
    toast.success("Delivery received");
    setReceiveRows({});
    load();
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-purchase-orders">
      <PageHeader
        title={po ? `Purchase Order #${po.id}` : "Purchase Order"}
        actions={
          <Button href="/portal/pharmacy/purchase-orders" variant="ghost">
            <ChevronLeft size={15} /> Back to Purchase Orders
          </Button>
        }
      />
      {loading && (
        <div className="space-y-3">
          <SkeletonCard lines={4} />
          <SkeletonCard lines={3} />
        </div>
      )}
      {!loading && !po && <p className="text-hint text-[13px]">No such purchase order.</p>}
      {po && (
        <div className="space-y-space-4">
          <Card className="p-space-5">
            <div className="gap-space-4 grid grid-cols-2 sm:grid-cols-4">
              <div>
                <p className="text-hint text-[11.5px]">Supplier</p>
                <p className="text-ink-900 font-semibold">{po.supplier_name}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Order Date</p>
                <p className="text-ink-900 font-semibold">{formatDate(po.order_date)}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Total</p>
                <p className="text-ink-900 font-semibold">{po.total_amount != null ? formatINR(po.total_amount) : "—"}</p>
              </div>
              <div>
                <p className="text-hint text-[11.5px]">Status</p>
                <Badge tone={PO_STATUS_TONES[po.status]}>{PO_STATUS_LABELS[po.status]}</Badge>
              </div>
            </div>
            {po.notes && <p className="text-hint mt-space-3 text-[12.5px]">{po.notes}</p>}
          </Card>

          <Card className="p-space-5">
            <p className="text-ink-900 mb-space-3 text-[15px] font-semibold">Items</p>
            <div className="space-y-space-3">
              {po.items.map((item) => {
                const remaining = item.quantity_ordered - item.quantity_received;
                const row = receiveRows[item.id] || { batch_number: "", expiry_date: "", quantity_received: "" };
                return (
                  <div key={item.id} className="border-line p-space-3 rounded-md border">
                    <div className="gap-space-2 flex items-center justify-between">
                      <p className="text-ink-900 font-semibold">{item.medicine_name}</p>
                      <p className="text-hint text-[12px]">
                        Ordered {item.quantity_ordered} · Received {item.quantity_received}
                        {remaining > 0 && ` · ${remaining} remaining`}
                      </p>
                    </div>
                    {canWrite && remaining > 0 && po.status !== "delivered" && po.status !== "cancelled" && (
                      <div className="gap-space-2 mt-space-2 grid grid-cols-3">
                        <Input
                          placeholder="Batch number" value={row.batch_number}
                          onChange={(e) => updateRow(item.id, { batch_number: e.target.value })}
                        />
                        <Input
                          type="date" placeholder="Expiry date" value={row.expiry_date}
                          onChange={(e) => updateRow(item.id, { expiry_date: e.target.value })}
                        />
                        <Input
                          type="number" min="1" max={remaining} placeholder="Qty received" value={row.quantity_received}
                          onChange={(e) => updateRow(item.id, { quantity_received: e.target.value })}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {canWrite && po.status !== "delivered" && po.status !== "cancelled" && (
              <Button disabled={submitting} onClick={handleReceive} className="mt-space-4">
                {submitting ? "Receiving…" : "Receive Delivery"}
              </Button>
            )}
          </Card>
        </div>
      )}
    </PortalShell>
  );
}
