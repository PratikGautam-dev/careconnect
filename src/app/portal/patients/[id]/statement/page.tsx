"use client";

import { useParams } from "next/navigation";
import { ChevronLeft, Printer } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatDate, formatShortDateTime } from "@/lib/formatDate";
import { formatINR } from "@/lib/formatCurrency";
import { usePatientDetail } from "@/hooks/usePatientDetail";
import { BILL_TYPE_LABELS, PAYMENT_STATUS_LABELS } from "../../../billing/_components/billing-overview-columns";

/** "Generate Patient Statement" -- same window.print()-on-live-HTML
 * precedent as /portal/pharmacy-billing/[id]'s own "Print Invoice" (no
 * dedicated print CSS/PDF library anywhere in this codebase; this follows
 * that exact pattern rather than introducing a new one). A full statement
 * across BOTH billing domains for one patient, not any single bill. */
export default function PatientStatementPage() {
  const params = useParams<{ id: string }>();
  const { hospital, ready } = usePortalGuard();
  const { data } = usePatientDetail(params.id, ready);

  if (!hospital) return null;

  const patient = data?.patient;
  const billing = data?.billing;
  const rows = billing?.transactions ?? [];

  return (
    <PortalShell hospital={hospital} active="patients">
      <PageHeader
        title="Patient Statement"
        actions={
          <div className="gap-space-2 flex">
            <Button href={`/portal/patients/${params.id}`} variant="ghost">
              <ChevronLeft size={15} /> Back to Patient
            </Button>
            {patient && (
              <Button variant="secondary" onClick={() => window.print()}>
                <Printer size={15} /> Print Statement
              </Button>
            )}
          </div>
        }
      />

      {!data ? (
        <p className="text-hint text-[13px]">Loading…</p>
      ) : (
        <Card className="p-space-6 mx-auto max-w-3xl">
          <div className="mb-space-5 flex items-start justify-between">
            <div>
              <h2 className="text-ink-900 text-[18px] font-bold">{hospital.name}</h2>
              <p className="text-hint">Billing Statement</p>
            </div>
            <p className="text-hint text-right">Generated {formatDate(new Date().toISOString())}</p>
          </div>

          <div className="border-line mb-space-5 grid grid-cols-2 gap-3 rounded-md border p-4 text-[12.5px]">
            <div><span className="text-ink-400">Patient:</span> <span className="text-ink-900 font-semibold">{patient!.name || patient!.phone}</span></div>
            <div><span className="text-ink-400">Phone:</span> <span className="text-ink-900 font-semibold">{patient!.phone}</span></div>
            <div><span className="text-ink-400">Patient ID:</span> <span className="text-ink-900 font-mono font-semibold">{patient!.patient_display_id || "—"}</span></div>
            <div><span className="text-ink-400">MRN:</span> <span className="text-ink-900 font-mono font-semibold">{patient!.mrn || "—"}</span></div>
          </div>

          <table className="mb-space-5 w-full text-[12.5px]">
            <thead>
              <tr className="border-line text-hint border-b text-left">
                <th className="py-space-2 font-semibold">Invoice</th>
                <th className="py-space-2 font-semibold">Type</th>
                <th className="py-space-2 font-semibold">Date</th>
                <th className="py-space-2 text-right font-semibold">Amount</th>
                <th className="py-space-2 text-right font-semibold">Paid</th>
                <th className="py-space-2 text-right font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-line divide-y">
              {rows.length === 0 ? (
                <tr><td colSpan={6} className="text-hint py-space-4 text-center">No bills for this patient.</td></tr>
              ) : rows.map((r) => (
                <tr key={`${r.bill_type}-${r.id}`}>
                  <td className="py-space-2 font-mono">{r.invoice_ref}</td>
                  <td className="py-space-2">{BILL_TYPE_LABELS[r.bill_type]}</td>
                  <td className="py-space-2">{formatShortDateTime(r.date)}</td>
                  <td className="py-space-2 text-right">{formatINR(r.amount)}</td>
                  <td className="py-space-2 text-right">{formatINR(r.amount_paid)}</td>
                  <td className="py-space-2 text-right"><Badge tone={r.payment_status === "paid" ? "success" : "clay"}>{PAYMENT_STATUS_LABELS[r.payment_status] ?? r.payment_status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>

          {billing && (
            <div className="border-line ml-auto w-full max-w-xs space-y-space-2 rounded-md border p-4 text-[13px]">
              <div className="flex justify-between"><span className="text-ink-600">Total Billed</span><span className="text-ink-900 font-semibold">{formatINR(billing.stats.total_amount)}</span></div>
              <div className="flex justify-between"><span className="text-ink-600">Total Paid</span><span className="text-success font-semibold">{formatINR(billing.stats.total_paid)}</span></div>
              <div className="border-line flex justify-between border-t pt-space-2 font-bold"><span className="text-ink-700">Pending Dues</span><span className="text-clay-700">{formatINR(billing.stats.pending_dues)}</span></div>
            </div>
          )}

          {patient!.billing_notes && (
            <p className="text-hint mt-space-5 text-[12px]"><span className="font-semibold">Notes:</span> {patient!.billing_notes}</p>
          )}
        </Card>
      )}
    </PortalShell>
  );
}
